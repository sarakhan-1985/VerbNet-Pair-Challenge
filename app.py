import os, sqlite3, secrets, time
from pathlib import Path
import streamlit as st
from questions import QUESTIONS

DB = Path(os.getenv('VERBNET_DB_PATH', str(Path(__file__).with_name('challenge.sqlite3'))))
TEAM_COUNT = 6

st.set_page_config(page_title='VerbNet Pair Challenge', page_icon='🏆', layout='wide')

def connect():
    conn = sqlite3.connect(DB, timeout=20, isolation_level=None)
    conn.row_factory = sqlite3.Row
    conn.execute('PRAGMA busy_timeout=20000')
    conn.execute('PRAGMA journal_mode=WAL')
    return conn

def init():
    with connect() as c:
        c.execute('CREATE TABLE IF NOT EXISTS rounds (id INTEGER PRIMARY KEY, code TEXT UNIQUE NOT NULL, status TEXT NOT NULL, created_at INTEGER NOT NULL)')
        c.execute('CREATE TABLE IF NOT EXISTS teams (id INTEGER PRIMARY KEY, round_id INTEGER NOT NULL, name TEXT NOT NULL, pin TEXT NOT NULL, submitted_at INTEGER, UNIQUE(round_id,name))')
        c.execute('CREATE TABLE IF NOT EXISTS answers (team_id INTEGER NOT NULL, q_index INTEGER NOT NULL, answer INTEGER NOT NULL, PRIMARY KEY(team_id,q_index))')
init()

def active_round(c):
    return c.execute('SELECT * FROM rounds ORDER BY id DESC LIMIT 1').fetchone()

def progress(c, rid):
    return c.execute('SELECT * FROM teams WHERE round_id=? ORDER BY id', (rid,)).fetchall()

def score(c, tid):
    ans = {r['q_index']: r['answer'] for r in c.execute('SELECT q_index,answer FROM answers WHERE team_id=?',(tid,))}
    return sum(ans.get(i)==q[3] for i,q in enumerate(QUESTIONS))

def results(c, rid):
    return sorted([(t['name'], score(c,t['id']),t['submitted_at'] is not None) for t in progress(c,rid)], key=lambda x:(-x[1],x[0].lower()))

st.title('🏆 VerbNet Pair Challenge')
st.caption('Six teams · 20 introductory semantic-role questions · Results revealed only by instructor')
role = st.sidebar.radio('Access', ['Team','Instructor'])

if role == 'Instructor':
    with connect() as c:
        rnd = active_round(c)
        if not rnd or rnd['status']=='revealed':
            if st.button('Create a new round',type='primary'):
                code=secrets.token_hex(3).upper()
                c.execute('INSERT INTO rounds(code,status,created_at) VALUES (?,?,?)',(code,'open',int(time.time())))
                st.rerun()
        if rnd:
            st.subheader(f"Round code: {rnd['code']}")
            st.write(f"Status: **{rnd['status'].title()}**")
            teams=progress(c,rnd['id'])
            st.metric('Submitted teams',f"{sum(t['submitted_at'] is not None for t in teams)}/{TEAM_COUNT}")
            st.dataframe([{'Team':t['name'],'Submission':'Submitted' if t['submitted_at'] else 'Working'} for t in teams],hide_index=True,use_container_width=True)
            if rnd['status']=='open':
                if len(teams)==TEAM_COUNT and all(t['submitted_at'] for t in teams):
                    st.success('All six teams submitted. You may now reveal results.')
                    if st.button('Reveal results to all teams',type='primary'):
                        c.execute("UPDATE rounds SET status='revealed' WHERE id=?",(rnd['id'],))
                        st.rerun()
                else:
                    st.info('Reveal is locked until all six teams submit. You may close the round early if needed.')
                    if st.checkbox('I confirm that I want to close this round early'):
                        if st.button('Close round and reveal (unfinished teams score zero)'):
                            c.execute('BEGIN IMMEDIATE')
                            c.execute('DELETE FROM answers WHERE team_id IN (SELECT id FROM teams WHERE round_id=? AND submitted_at IS NULL)',(rnd['id'],))
                            c.execute("UPDATE rounds SET status='revealed' WHERE id=?",(rnd['id'],))
                            c.execute('COMMIT')
                            st.rerun()
            if rnd['status']=='revealed':
                leaderboard=results(c,rnd['id'])
                st.subheader('Final leaderboard')
                st.dataframe([{'Rank':1+sum(x[1]>s for x in leaderboard),'Team':n,'Score / 20':s,'Submitted':done} for n,s,done in leaderboard],hide_index=True,use_container_width=True)
                st.download_button('Download scores (CSV)',data='Team,Score,Submitted\n'+''.join(f'{n},{s},{done}\n' for n,s,done in leaderboard),file_name='verbnet_scores.csv',mime='text/csv')
                st.subheader('Projector answer review')
                selected=st.selectbox('Question',list(range(len(QUESTIONS))),format_func=lambda x:f'Question {x+1}')
                sentence,prompt,opts,correct,explanation=QUESTIONS[selected]
                st.write('**Sentence:**',sentence)
                st.write('**Question:**',prompt)
                st.success(f'Correct answer: {opts[correct]}')
                st.write(explanation)
    if st.button('Refresh dashboard'):
        st.rerun()
else:
    with connect() as c:
        rnd=active_round(c)
        if not rnd:
            st.info('Waiting for the instructor to create a round.')
            st.stop()
        if 'team_id' not in st.session_state or st.session_state.get('round_id')!=rnd['id']:
            with st.form('join'):
                code=st.text_input('Session code').strip().upper()
                name=st.text_input('Team name (e.g., Team A)').strip()
                go=st.form_submit_button('Join or resume')
            if go:
                if code != rnd['code']:
                    st.error('Incorrect session code.')
                elif not name or len(name)>40:
                    st.error('Enter a team name (up to 40 characters).')
                else:
                    existing=c.execute('SELECT * FROM teams WHERE round_id=? AND name=?',(rnd['id'],name)).fetchone()
                    if existing:
                        st.session_state.team_id=existing['id']
                        st.session_state.round_id=rnd['id']
                        st.rerun()
                    elif rnd['status']!='open':
                        st.error('Round is closed.')
                    else:
                        try:
                            c.execute('BEGIN IMMEDIATE')
                            count=c.execute('SELECT COUNT(*) FROM teams WHERE round_id=?',(rnd['id'],)).fetchone()[0]
                            if count>=TEAM_COUNT:
                                c.execute('ROLLBACK')
                                st.error('All six team slots are taken.')
                            else:
                                cur=c.execute('INSERT INTO teams(round_id,name,pin) VALUES (?,?,?)',(rnd['id'],name,''))
                                c.execute('COMMIT')
                                st.session_state.team_id=cur.lastrowid
                                st.session_state.round_id=rnd['id']
                                st.rerun()
                        except sqlite3.IntegrityError:
                            c.execute('ROLLBACK')
                            st.error('Team name already exists; choose your team name to resume.')
            st.stop()
        team=c.execute('SELECT * FROM teams WHERE id=? AND round_id=?',(st.session_state.team_id,rnd['id'])).fetchone()
        if not team:
            st.session_state.pop('team_id',None)
            st.rerun()
        st.subheader(team['name'])
        if rnd['status']=='revealed':
            board=results(c,rnd['id'])
            st.subheader('Final leaderboard')
            st.dataframe([{'Rank':1+sum(x[1]>s for x in board),'Team':n,'Score / 20':s} for n,s,_ in board],hide_index=True,use_container_width=True)
            ans={r['q_index']:r['answer'] for r in c.execute('SELECT q_index,answer FROM answers WHERE team_id=?',(team['id'],))}
            for i,(sentence,prompt,opts,correct,explanation) in enumerate(QUESTIONS):
                with st.expander(f'Question {i+1}: {prompt}'):
                    st.write(sentence)
                    st.write('Your answer:',opts[ans[i]] if i in ans else 'Not answered')
                    st.write('Correct answer:',opts[correct])
                    st.write(explanation)
            st.stop()
        if team['submitted_at']:
            st.success('Submitted! Your answers and score will remain hidden until the instructor reveals the results.')
            if st.button('Check whether results are available'):
                st.rerun()
            st.stop()
        if rnd['status']!='open':
            st.info('This round has closed.')
            st.stop()
        st.info('Discuss answers with your partner. No scores or explanations appear before instructor reveal.')
        with st.form('quiz'):
            responses=[]
            for i,(sentence,prompt,opts,correct,explanation) in enumerate(QUESTIONS):
                st.markdown(f'**Q{i+1}. {sentence}**')
                responses.append(st.radio(prompt,['Select an answer']+opts,key=f'question_{rnd["id"]}_{i}',index=0))
            submit=st.form_submit_button('Submit final answers')
        if submit:
            if any(a=='Select an answer' for a in responses):
                st.error('Please answer all 20 questions before submitting.')
            else:
                c.execute('BEGIN IMMEDIATE')
                fresh=c.execute('SELECT submitted_at FROM teams WHERE id=?',(team['id'],)).fetchone()
                current=c.execute('SELECT status FROM rounds WHERE id=?',(rnd['id'],)).fetchone()
                if fresh['submitted_at'] is not None or current['status']!='open':
                    c.execute('ROLLBACK')
                    st.error('Submission is already recorded or the round has closed.')
                else:
                    for i,(_,_,opts,_,_) in enumerate(QUESTIONS):
                        c.execute('INSERT INTO answers(team_id,q_index,answer) VALUES (?,?,?)',(team['id'],i,opts.index(responses[i])))
                    c.execute('UPDATE teams SET submitted_at=? WHERE id=?',(int(time.time()),team['id']))
                    c.execute('COMMIT')
                    st.rerun()
