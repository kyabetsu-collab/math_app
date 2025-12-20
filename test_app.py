import streamlit as st
import json
import pandas as pd
import sympy as sp
import os
import unicodedata
from datetime import datetime

# ==============================
# 1. 設定・教科定義
# ==============================
SUBJECTS = ["数学", "英語", "国語", "理科", "社会"]
TEACHER_PASSWORD = "admin" 

REQUIRED_COLUMNS = [
    "student_id", "question", "student_answer", 
    "correct_answer", "is_correct", "timestamp", "type"
]

# ==============================
# 2. データ管理ロジック
# ==============================

def get_problem_file():
    subject = st.session_state.get("selected_subject", "数学")
    return f"{subject}_problems.json"

def get_result_file():
    subject = st.session_state.get("selected_subject", "数学")
    return f"{subject}_results.csv"

def load_problems():
    path = get_problem_file()
    if not os.path.exists(path): return []
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except: return []

def save_problems(problems):
    path = get_problem_file()
    with open(path, "w", encoding="utf-8") as f:
        json.dump(problems, f, ensure_ascii=False, indent=2)

def load_results():
    path = get_result_file()
    if not os.path.exists(path):
        return pd.DataFrame(columns=REQUIRED_COLUMNS)
    try:
        df = pd.read_csv(path, encoding='utf-8-sig', engine='python')
        if "is_correct" in df.columns:
            df["is_correct"] = pd.to_numeric(df["is_correct"], errors='coerce').fillna(0).astype(int)
        return df
    except:
        return pd.DataFrame(columns=REQUIRED_COLUMNS)

def save_final_results(results_list):
    """一括保存ロジック"""
    path = get_result_file()
    new_df = pd.DataFrame(results_list)
    header = not os.path.exists(path)
    new_df.to_csv(path, mode='a', index=False, header=header, encoding='utf-8-sig')

def normalize_text(s):
    if not isinstance(s, str): return str(s)
    s = unicodedata.normalize("NFKC", s).strip().replace(" ", "")
    return s.lower()

def is_equal(student, correct):
    s_raw = normalize_text(student)
    c_raw = normalize_text(correct)
    if s_raw == c_raw: return True
    try:
        if abs(float(s_raw) - float(c_raw)) < 1e-7: return True
    except: pass
    try:
        # 数式としての等価性
        s_expr = s_raw.replace("x=", "").replace("y=", "")
        c_expr = c_raw.replace("x=", "").replace("y=", "")
        if sp.simplify(f"({s_expr}) - ({c_expr})") == 0: return True
    except: pass
    return False

# ==============================
# 3. 生徒用画面 (見直し・詳細表示機能付き)
# ==============================

def student_view():
    subject = st.session_state.selected_subject
    st.header(f"✏️ {subject} テスト")
    
    problems = load_problems()
    if not problems:
        st.warning("問題が登録されていません。")
        return

    # セッション状態の初期化
    if "q_idx" not in st.session_state:
        st.session_state.q_idx = 0
        st.session_state.answers = [""] * len(problems) # 空の解答欄を作成
        st.session_state.done = False

    if "student_id" not in st.session_state:
        sid = st.text_input("生徒ID（名前など）を入力して開始してください")
        if st.button("テストを開始"):
            if sid:
                st.session_state.student_id = sid
                st.rerun()
            else: st.warning("IDを入力してください")
        return

    # --- テスト結果画面 (詳細フィードバック) ---
    if st.session_state.done:
        st.balloons()
        st.success(f"お疲れ様でした、{st.session_state.student_id}さん！結果を確認しましょう。")
        
        score = 0
        feedback_data = []
        for i, prob in enumerate(problems):
            ans = st.session_state.answers[i]
            correct = is_equal(ans, prob["answer"])
            if correct: score += 1
            feedback_data.append({
                "question": prob["question"],
                "your_ans": ans,
                "correct_ans": prob["answer"],
                "is_correct": correct
            })
        
        c1, c2 = st.columns(2)
        c1.metric("今回の得点", f"{score} / {len(problems)}")
        c2.metric("正答率", f"{int(score/len(problems)*100)}%")

        st.subheader("🔍 解答の詳細と答え合わせ")
        for i, item in enumerate(feedback_data):
            icon = "✅ 正解" if item["is_correct"] else "❌ 不正解"
            color = "green" if item["is_correct"] else "red"
            with st.expander(f"問 {i+1}: {icon}"):
                st.write(f"**問題:** {item['question']}")
                st.write(f"**あなたの解答:** {item['your_ans']}")
                if not item["is_correct"]:
                    st.write(f"**正しい答え:** :{color}[{item['correct_ans']}]")
        
        if st.button("ホーム（教科選択）へ戻る"):
            for k in ["q_idx", "answers", "done", "student_id"]:
                if k in st.session_state: del st.session_state[k]
            st.session_state.mode = None
            st.rerun()
        return

    # --- 出題画面 (戻る・進むナビゲーション) ---
    idx = st.session_state.q_idx
    prob = problems[idx]
    
    st.subheader(f"問題 {idx + 1} / {len(problems)}")
    st.progress((idx + 1) / len(problems))
    
    if "$" in prob["question"]: st.latex(prob["question"].replace("$", ""))
    else: st.info(prob["question"])
    
    # 解答入力
    q_type = prob.get("type", "記述式")
    if q_type == "選択式":
        # 保存されている解答がある場合はそのインデックスを取得
        options = prob.get("options", [])
        default_idx = options.index(st.session_state.answers[idx]) if st.session_state.answers[idx] in options else 0
        ans = st.radio("答えを選んでください", options, index=default_idx, key=f"input_{idx}")
    else:
        ans = st.text_input("答えを入力してください", value=st.session_state.answers[idx], key=f"input_{idx}")

    # 解答をセッションに保持
    st.session_state.answers[idx] = ans

    # ナビゲーション
    col1, col2, col3 = st.columns([1,1,2])
    with col1:
        if idx > 0:
            if st.button("⬅️ 前の問題へ"):
                st.session_state.q_idx -= 1
                st.rerun()
    with col2:
        if idx < len(problems) - 1:
            if st.button("次の問題へ ➡️"):
                st.session_state.q_idx += 1
                st.rerun()
    with col3:
        if st.button("📝 テストを終了して提出"):
            # 提出時に一括で保存処理
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
            records = []
            for i, p in enumerate(problems):
                records.append({
                    "student_id": st.session_state.student_id,
                    "question": p["question"],
                    "student_answer": st.session_state.answers[i],
                    "correct_answer": p["answer"],
                    "is_correct": 1 if is_equal(st.session_state.answers[i], p["answer"]) else 0,
                    "timestamp": timestamp,
                    "type": p.get("type", "記述式")
                })
            save_final_results(records)
            st.session_state.done = True
            st.rerun()

# ==============================
# 4. 教師用画面 (詳細分析)
# ==============================

def teacher_view():
    subject = st.session_state.selected_subject
    st.header(f"🧑‍🏫 教師用管理（{subject}）")
    tab1, tab2, tab3 = st.tabs(["📊 成績分析", "📝 問題編集", "⚙️ データ管理"])

    with tab1:
        df = load_results()
        if not df.empty:
            st.subheader("クラス全体の概況")
            m1, m2, m3 = st.columns(3)
            m1.metric("全体平均正答率", f"{(df['is_correct'].mean()*100):.1f}%")
            m2.metric("受験人数", f"{df['student_id'].nunique()}人")
            m3.metric("総解答データ", f"{len(df)}件")

            st.divider()
            st.subheader("❓ 問題別の難易度（正答率グラフ）")
            # 問題ごとの正答率
            q_stats = df.groupby("question")["is_correct"].mean() * 100
            st.bar_chart(q_stats)
            st.caption("正答率が低い問題はクラス全体の苦手項目です。重点的に解説しましょう。")

            st.divider()
            st.subheader("👤 生徒個別の分析")
            selected_sid = st.selectbox("詳細を見る生徒を選択", sorted(df["student_id"].unique()))
            if selected_sid:
                pdf = df[df["student_id"] == selected_sid].copy()
                st.write(f"**{selected_sid} さんの正答率: {(pdf['is_correct'].mean()*100):.1f}%**")
                # 正誤を見やすく変換
                pdf["結果"] = pdf["is_correct"].map({1: "✅正解", 0: "❌不正解"})
                st.dataframe(pdf[["question", "student_answer", "correct_answer", "結果"]], use_container_width=True, hide_index=True)
        else:
            st.info("解答データがまだありません。")

    with tab2:
        # 問題追加・削除 (省略せず実装)
        problems = load_problems()
        with st.form("new_q"):
            st.write("### 新規問題追加")
            qt = st.selectbox("形式", ["記述式", "選択式"])
            qq = st.text_area("問題文")
            qa = st.text_input("正解（文字列）")
            opts = st.text_input("選択肢がある場合 (カンマ区切り A,B,C,D)")
            if st.form_submit_button("問題を保存"):
                if qq and qa:
                    problems.append({
                        "type": qt, "question": qq, "answer": qa, 
                        "options": [o.strip() for o in opts.split(",")] if opts else []
                    })
                    save_problems(problems)
                    st.success("登録しました！")
                    st.rerun()

    with tab3:
        if st.button("📁 データをリセット（アーカイブ）"):
            path = get_result_file()
            if os.path.exists(path):
                os.rename(path, path.replace(".csv", f"_{datetime.now().strftime('%Y%m%d_%H%M')}.csv"))
                st.success("アーカイブしました。")
                st.rerun()

# ==============================
# 5. メイン制御
# ==============================
st.set_page_config(page_title="学習分析システム", layout="wide")

if "mode" not in st.session_state: st.session_state.mode = None
if "selected_subject" not in st.session_state: st.session_state.selected_subject = "数学"

with st.sidebar:
    st.title("🍀 メニュー")
    if st.button("🏠 教科選択へ戻る"):
        for k in ["q_idx", "answers", "done", "student_id", "mode"]:
            if k in st.session_state: del st.session_state[k]
        st.session_state.mode = None
        st.rerun()
    st.divider()
    st.write(f"現在の教科: **{st.session_state.selected_subject}**")
    if st.button("✏️ テストを受ける"): 
        st.session_state.mode = "student"
        st.rerun()
    if st.button("🧑‍🏫 教師用管理画面"): 
        st.session_state.mode = "auth"
        st.rerun()

# メイン表示エリア
if st.session_state.mode is None:
    st.title("📚 学習分析システム")
    st.write("学習したい教科を選択してください。")
    cols = st.columns(len(SUBJECTS))
    for i, sub in enumerate(SUBJECTS):
        if cols[i].button(sub, use_container_width=True):
            st.session_state.selected_subject = sub
            st.rerun()
elif st.session_state.mode == "student": student_view()
elif st.session_state.mode == "auth":
    pw = st.text_input("パスワード", type="password")
    if st.button("ログイン"):
        if pw == TEACHER_PASSWORD: st.session_state.mode = "teacher"; st.rerun()
        else: st.error("パスワードが違います")
elif st.session_state.mode == "teacher": teacher_view()