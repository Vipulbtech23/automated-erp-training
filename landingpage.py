import streamlit as st

st.set_page_config(
    page_title="LIET Smart ERP + LMS",
    page_icon="🎓",
    layout="wide",
    initial_sidebar_state="collapsed",
)

ADMIN_URL = "https://automated-erp-training-teacher.streamlit.app/"
STUDENT_URL = "https://automated-erp-training-student.streamlit.app/"
COLLEGE_URL = "https://www.lloydcollege.in/"

st.markdown(r'''
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&family=Playfair+Display:wght@700;800&display=swap');

:root {
  --navy:#05152f; --blue:#0d47a1; --cyan:#11cbd7; --gold:#f7b733;
  --orange:#ef6c00; --soft:#dceaff; --glass:rgba(255,255,255,.11);
}
html { scroll-behavior:smooth; }
body,.stApp { font-family:'Inter',sans-serif; }
.stApp {
  color:#fff;
  background:
    radial-gradient(circle at 10% 20%,rgba(17,203,215,.18),transparent 30%),
    radial-gradient(circle at 90% 10%,rgba(247,183,51,.16),transparent 25%),
    linear-gradient(135deg,#031126 0%,#082b5d 50%,#07465a 100%);
  overflow-x:hidden;
}
[data-testid="stHeader"]{background:transparent}
.block-container{max-width:1450px;padding-top:1rem;padding-bottom:0}
#MainMenu,footer{visibility:hidden}

.navbar{
  position:sticky;top:.5rem;z-index:1000;display:flex;align-items:center;
  justify-content:space-between;gap:1rem;padding:.95rem 1.3rem;border-radius:20px;
  border:1px solid rgba(255,255,255,.2);background:rgba(5,24,60,.76);
  backdrop-filter:blur(18px);box-shadow:0 15px 40px rgba(0,0,0,.24);
  animation:drop .8s ease both;
}
.brand{display:flex;align-items:center;gap:.8rem}.brand-icon{width:46px;height:46px;
  display:grid;place-items:center;border-radius:14px;font-size:1.55rem;
  background:linear-gradient(135deg,var(--gold),var(--orange));}
.brand-title{font-size:1.15rem;font-weight:800}.brand-sub{font-size:.72rem;color:var(--soft)}
.navlinks{display:flex;gap:.45rem}.navlinks a{color:white!important;text-decoration:none!important;
  padding:.58rem .8rem;border-radius:10px;font-weight:600;font-size:.88rem;transition:.25s}
.navlinks a:hover{background:rgba(255,255,255,.12);transform:translateY(-2px)}

.hero{min-height:650px;display:grid;grid-template-columns:1.15fr .85fr;align-items:center;
  gap:2.5rem;padding:4.6rem 1rem 3rem}.hero-copy{animation:rise .95s ease both}
.eyebrow{display:inline-flex;padding:.65rem 1rem;border-radius:999px;border:1px solid rgba(255,255,255,.2);
  background:rgba(255,255,255,.08);color:#ffe0a3;font-weight:700;font-size:.88rem;margin-bottom:1.25rem}
.hero h1{font-family:'Playfair Display',serif;font-size:clamp(3rem,6vw,5.8rem);line-height:1.02;
  margin:0;letter-spacing:-1.5px;background:linear-gradient(90deg,#fff,#d7edff,#ffd784,#7ef9ff);
  -webkit-background-clip:text;-webkit-text-fill-color:transparent}
.hero p{margin-top:1.35rem;color:var(--soft);font-size:1.08rem;line-height:1.85;max-width:780px}
.ctas{display:flex;flex-wrap:wrap;gap:1rem;margin-top:2rem}.btn{display:inline-flex;align-items:center;justify-content:center;
  min-width:210px;padding:.95rem 1.3rem;border-radius:14px;text-decoration:none!important;color:white!important;
  font-weight:800;box-shadow:0 14px 35px rgba(0,0,0,.28);transition:.3s}.btn:hover{transform:translateY(-5px) scale(1.02)}
.admin{background:linear-gradient(135deg,#f78c19,#ef4d36)}.student{background:linear-gradient(135deg,#00b894,#00a8e8)}
.college{background:linear-gradient(135deg,#4a69bd,#6c5ce7)}

.visual{position:relative;min-height:490px}.orbit{position:absolute;inset:40px 35px;border-radius:36px;
  background:linear-gradient(150deg,rgba(255,255,255,.18),rgba(255,255,255,.05));
  border:1px solid rgba(255,255,255,.24);box-shadow:0 30px 80px rgba(0,0,0,.35);
  backdrop-filter:blur(22px);display:grid;place-items:center;text-align:center;padding:2rem;overflow:hidden}
.college-icon{font-size:7.5rem;animation:float 3.2s ease-in-out infinite;filter:drop-shadow(0 20px 35px rgba(0,0,0,.3))}
.visual-title{font-size:1.7rem;font-weight:800}.visual-copy{color:var(--soft);margin-top:.65rem;line-height:1.7}
.chip{position:absolute;padding:.8rem 1rem;border-radius:14px;border:1px solid rgba(255,255,255,.23);
  background:rgba(255,255,255,.13);backdrop-filter:blur(14px);font-weight:700;box-shadow:0 12px 28px rgba(0,0,0,.2);
  animation:float 3.6s ease-in-out infinite}.c1{left:0;top:88px}.c2{right:0;top:155px;animation-delay:.8s}
.c3{left:15px;bottom:65px;animation-delay:1.4s}.c4{right:10px;bottom:35px;animation-delay:2s}

.section{padding:4rem 1rem}.head{text-align:center;max-width:850px;margin:0 auto 2.3rem}.kicker{color:#ffd47b;
  text-transform:uppercase;letter-spacing:2px;font-size:.78rem;font-weight:800}.title{font-family:'Playfair Display',serif;
  font-size:clamp(2.2rem,4vw,3.6rem);line-height:1.15;margin:.55rem 0 .8rem}.copy{color:var(--soft);line-height:1.8}
.grid3,.grid4{display:grid;gap:1.2rem}.grid3{grid-template-columns:repeat(3,1fr)}.grid4{grid-template-columns:repeat(4,1fr)}
.card{padding:1.55rem;min-height:220px;border-radius:22px;border:1px solid rgba(255,255,255,.2);
  background:var(--glass);backdrop-filter:blur(16px);box-shadow:0 18px 45px rgba(0,0,0,.22);transition:.3s}
.card:hover{transform:translateY(-9px);background:rgba(255,255,255,.16)}.icon{width:52px;height:52px;display:grid;place-items:center;
  border-radius:15px;font-size:1.55rem;background:linear-gradient(135deg,var(--gold),var(--orange));margin-bottom:1rem}
.card h3{margin:0 0 .7rem;font-size:1.2rem}.card p{color:var(--soft);line-height:1.72;font-size:.92rem}
.stat{text-align:center;padding:1.45rem 1rem;border-radius:20px;border:1px solid rgba(255,255,255,.2);
  background:rgba(255,255,255,.1)}.value{font-size:2.25rem;font-weight:900;color:#7ef9ff}.label{margin-top:.4rem;color:var(--soft);font-weight:600}

.about{display:grid;grid-template-columns:.95fr 1.05fr;gap:2rem;align-items:center;padding:2.2rem;border-radius:28px;
  border:1px solid rgba(255,255,255,.2);background:linear-gradient(135deg,rgba(255,255,255,.15),rgba(255,255,255,.06));
  box-shadow:0 24px 60px rgba(0,0,0,.26)}.about-visual{min-height:340px;display:grid;place-items:center;border-radius:24px;
  background:linear-gradient(135deg,rgba(13,71,161,.65),rgba(5,24,60,.7));border:1px solid rgba(255,255,255,.18)}
.about-big{font-size:8rem;animation:float 3.4s ease-in-out infinite}.about h2{font-family:'Playfair Display',serif;font-size:2.7rem;margin:0 0 1rem}
.about p{color:var(--soft);line-height:1.85}.points{display:grid;grid-template-columns:1fr 1fr;gap:.8rem;margin-top:1.2rem}
.point{padding:.85rem 1rem;border-radius:13px;background:rgba(255,255,255,.08);border:1px solid rgba(255,255,255,.13);font-weight:650}

.workflow{display:grid;grid-template-columns:repeat(4,1fr);gap:1rem}.step{padding:1.4rem;border-radius:19px;border:1px solid rgba(255,255,255,.2);
  background:rgba(255,255,255,.1);text-align:center}.stepno{width:42px;height:42px;margin:0 auto .8rem;display:grid;place-items:center;
  border-radius:50%;background:linear-gradient(135deg,var(--gold),var(--orange));font-weight:900;color:#071a3d}.step p{color:var(--soft);font-size:.9rem;line-height:1.6}

.contact{text-align:center;padding:2.6rem 1.4rem;border-radius:28px;border:1px solid rgba(255,255,255,.2);
  background:linear-gradient(135deg,rgba(13,71,161,.55),rgba(0,168,232,.25));box-shadow:0 24px 60px rgba(0,0,0,.25)}
.contact h2{font-family:'Playfair Display',serif;font-size:2.8rem;margin:0 0 .9rem}.contact p{color:var(--soft);max-width:850px;margin:0 auto 1.3rem;line-height:1.8}
.footerbox{margin-top:3rem;padding:2.3rem 1rem;border-radius:28px 28px 0 0;text-align:center;background:rgba(1,12,34,.62);color:var(--soft)}

.dot{position:fixed;width:16px;height:16px;border-radius:50%;background:rgba(255,255,255,.22);animation:bubble 10s ease-in-out infinite;pointer-events:none}
.d1{left:5%;top:25%}.d2{left:88%;top:18%;animation-delay:2s}.d3{left:12%;top:78%;animation-delay:4s}.d4{left:77%;top:82%;animation-delay:1s}
@keyframes drop{from{opacity:0;transform:translateY(-24px)}to{opacity:1;transform:none}}
@keyframes rise{from{opacity:0;transform:translateY(38px)}to{opacity:1;transform:none}}
@keyframes float{0%,100%{transform:translateY(0)}50%{transform:translateY(-15px)}}
@keyframes bubble{0%,100%{transform:translateY(0) scale(1);opacity:.28}50%{transform:translateY(-120px) scale(1.5);opacity:.72}}
@media(max-width:980px){.navlinks{display:none}.hero,.about{grid-template-columns:1fr}.grid4,.workflow{grid-template-columns:repeat(2,1fr)}.grid3{grid-template-columns:1fr}}
@media(max-width:640px){.hero{min-height:auto;padding-top:3rem}.hero h1{font-size:3rem}.visual{min-height:390px}.orbit{inset:25px 10px}.college-icon{font-size:5.5rem}.grid4,.workflow,.points{grid-template-columns:1fr}.btn{width:100%}}
</style>
<div class="dot d1"></div><div class="dot d2"></div><div class="dot d3"></div><div class="dot d4"></div>
''', unsafe_allow_html=True)

st.markdown(f'''
<div class="navbar">
  <div class="brand"><div class="brand-icon">🎓</div><div><div class="brand-title">LIET Smart ERP + LMS</div><div class="brand-sub">Lloyd Institute of Engineering & Technology</div></div></div>
  <div class="navlinks"><a href="#home">Home</a><a href="#features">Features</a><a href="#about">About</a><a href="#workflow">Workflow</a><a href="#contact">Contact</a></div>
</div>

<section id="home" class="hero">
  <div class="hero-copy">
    <div class="eyebrow">✨ AI-Powered Academic Management Platform</div>
    <h1>Empowering Education Through Smart Technology</h1>
    <p>Welcome to the digital academic ecosystem of Lloyd Institute of Engineering & Technology. LIET Smart ERP + LMS integrates administration, learning, assessments, analytics, attendance, reporting and AI-driven academic mentoring into one unified platform.</p>
    <div class="ctas"><a class="btn admin" href="{ADMIN_URL}" target="_blank">👨‍🏫 Admin Dashboard</a><a class="btn student" href="{STUDENT_URL}" target="_blank">👨‍🎓 Student Dashboard</a><a class="btn college" href="{COLLEGE_URL}" target="_blank">🏛️ Official Website</a></div>
  </div>
  <div class="visual">
    <div class="orbit"><div><div class="college-icon">🏫</div><div class="visual-title">One Campus. One Smart Platform.</div><div class="visual-copy">Academic ERP, Learning Management System, AI Mentor, QR Attendance, Analytics and Automated Reports.</div></div></div>
    <div class="chip c1">🤖 AI Academic Officer</div><div class="chip c2">📚 Live Quiz Engine</div><div class="chip c3">📌 QR Attendance</div><div class="chip c4">📊 Smart Analytics</div>
  </div>
</section>
''', unsafe_allow_html=True)

st.markdown('''
<section class="section"><div class="grid4">
<div class="stat"><div class="value">500+</div><div class="label">Students Managed</div></div>
<div class="stat"><div class="value">1000+</div><div class="label">Quiz Questions</div></div>
<div class="stat"><div class="value">24×7</div><div class="label">Digital Learning Access</div></div>
<div class="stat"><div class="value">AI</div><div class="label">Academic Intelligence</div></div>
</div></section>

<section id="features" class="section"><div class="head"><div class="kicker">Platform Capabilities</div><h2 class="title">Everything Needed for a Modern Academic Campus</h2><p class="copy">A unified platform for administrators and students, designed to simplify workflows, improve transparency and deliver personalized academic support.</p></div>
<div class="grid3">
<div class="card"><div class="icon">👨‍🏫</div><h3>Professional Admin ERP</h3><p>Manage students, analytics, attendance, quizzes, reports, certificates, notifications and academic operations from one powerful dashboard.</p></div>
<div class="card"><div class="icon">👨‍🎓</div><h3>Personalized Student Portal</h3><p>Students can review performance, attempt quizzes, track attendance, download documents and follow their complete learning journey.</p></div>
<div class="card"><div class="icon">🧠</div><h3>AI Academic Officer</h3><p>Detect weak topics, identify at-risk students, predict outcomes and generate mentoring recommendations using intelligent analysis.</p></div>
<div class="card"><div class="icon">📚</div><h3>Advanced LMS Quiz Engine</h3><p>Schedule quizzes, control attempts, auto-save responses, display leaderboards and analyse topic-wise performance.</p></div>
<div class="card"><div class="icon">📌</div><h3>QR Attendance System</h3><p>Generate secure attendance sessions with scan limits, duplicate prevention, live tracking and downloadable reports.</p></div>
<div class="card"><div class="icon">🏅</div><h3>Gamification & Motivation</h3><p>Encourage learning through XP, levels, badges, streaks, achievements and competitive academic leaderboards.</p></div>
</div></section>

<section id="about" class="section"><div class="about"><div class="about-visual"><div class="about-big">🎓</div></div><div><div class="kicker">About LIET</div><h2>Lloyd Institute of Engineering & Technology</h2><p>Located in Greater Noida, Uttar Pradesh, LIET focuses on academic excellence, practical learning, innovation and industry-ready technical education. The Smart ERP + LMS initiative supports this vision through a connected, data-driven and student-centred digital ecosystem.</p><div class="points"><div class="point">✅ Industry-Oriented Learning</div><div class="point">✅ AI-Driven Academic Support</div><div class="point">✅ Transparent Performance Tracking</div><div class="point">✅ Modern Digital Campus</div></div></div></div></section>

<section id="workflow" class="section"><div class="head"><div class="kicker">How It Works</div><h2 class="title">A Simple, Connected Academic Workflow</h2></div><div class="workflow">
<div class="step"><div class="stepno">1</div><h4>Admin Manages</h4><p>Publish quizzes, generate QR sessions, analyse students and create reports.</p></div>
<div class="step"><div class="stepno">2</div><h4>Students Learn</h4><p>Attempt assessments, track progress and access learning resources.</p></div>
<div class="step"><div class="stepno">3</div><h4>AI Analyses</h4><p>Detect weak topics, identify risk and provide personalized recommendations.</p></div>
<div class="step"><div class="stepno">4</div><h4>Reports Update</h4><p>Rankings, gradecards, certificates, analytics and notifications stay connected.</p></div>
</div></section>
''', unsafe_allow_html=True)

st.markdown(f'''
<section class="section"><div class="head"><div class="kicker">Secure Access</div><h2 class="title">Choose Your Portal</h2><p class="copy">Enter the appropriate dashboard based on your role in the academic ecosystem.</p></div>
<div class="grid3">
<div class="card"><div class="icon">👨‍🏫</div><h3>Administrator Portal</h3><p>Manage academic operations, quizzes, analytics, attendance, documents and AI insights.</p><a class="btn admin" href="{ADMIN_URL}" target="_blank">Open Admin ERP</a></div>
<div class="card"><div class="icon">👨‍🎓</div><h3>Student Portal</h3><p>Review performance, attempt quizzes, use AI guidance and download documents.</p><a class="btn student" href="{STUDENT_URL}" target="_blank">Open Student ERP</a></div>
<div class="card"><div class="icon">🏛️</div><h3>Official College Website</h3><p>Visit the official LIET website for institutional information, programmes and admissions.</p><a class="btn college" href="{COLLEGE_URL}" target="_blank">Visit Official Site</a></div>
</div></section>

<section id="contact" class="section"><div class="contact"><div class="kicker">Contact & Support</div><h2>Built for a Smarter LIET Campus</h2><p>LIET Smart ERP + LMS connects academic management, digital learning, AI mentoring and student success into one responsive platform.</p><div class="ctas" style="justify-content:center"><a class="btn college" href="{COLLEGE_URL}" target="_blank">🌐 Explore LIET</a><a class="btn student" href="{STUDENT_URL}" target="_blank">🎓 Student Access</a></div></div></section>

<div class="footerbox"><h3 style="margin:0 0 .6rem;color:#fff">🎓 LIET Smart ERP + LMS</h3><p>Lloyd Institute of Engineering & Technology, Greater Noida, Uttar Pradesh</p><p>Python • Streamlit • Firebase Firestore • Gemini AI • Pandas • Plotly • ReportLab</p><p style="font-size:.82rem">© 2026 LIET Smart Academic Platform</p></div>
''', unsafe_allow_html=True)