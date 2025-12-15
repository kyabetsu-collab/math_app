# ==============================
# 数学学習アプリ【完全完成版】
# ==============================

import streamlit as st
import json, random, os, re, math
import pandas as pd
import sympy as sp
from datetime import datetime

# ==============================
# 設定
# ==============================
PROBLEM_FILE = "problems.json"
RESULT_FILE = "results.csv"
TEACHER_PASSWORD = "20020711"

# ==============================
# 共通
# ==============================
def now():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

def load_problems():
    if os.path.exists(PROBLEM_FILE):
        with open(PROBLEM_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return []

def save_problems(problems):
    with open(PROBLEM_FILE, "w", encoding="utf-8") as f:
        json.dump(problems, f, ensure_ascii=False, indent=2)

# ==============================
# 採点
# ==============================
def normalize(s):
    if not isinstance(s, str):
        return s
    s = s.replace("　", " ").strip()
    s = re.sub(r"\s+", "", s)
    return s

def is_equal(student, correct):
    try:
        return sp.simplify(sp.sympify(student) - sp.sympify(correct)) == 0
    except:
        try:
            return abs(float(student) - float(correct)) < 1e-6
        except:
            return normalize(student) == normalize(correct)

def check_answer(student, correct):
    if isinstance(correct, list):
        return any(is_equal(student, c) for c in correct)
    return is_equal(student, correct)

# ==============================
# 生徒画面
# ==============================
def student_view():
    st.header("✏ 生徒用テスト")
    sid = st.text_input("生徒ID")

    if not sid:
        return

    problems = load_problems()
    if not problems:
        st.info("問題がありません")
        return

    n = len(problems)

    if "order" not in st.session_state:
        st.session_state.order = list(range(n))
        random.shuffle(st.session_state.order)
        st.session_state.q = 0
        st.session_state.answers = {}

    idx = st.session_state.order[st.session_state.q]
    prob = problems[idx]

    st.subheader(f"問題 {st.session_state.q+1}/{n}")
    st.write(prob["question"])

    ans = st.text_input(
        "答え",
        value=st.session_state.answers.get(idx, ""),
        key=f"ans_{idx}"
    )

    st.session_state.answers[idx] = ans

    col1, col2 = st.columns(2)

    with col1:
        if st.button("前へ") and st.session_state.q > 0:
            st.session_state.q -= 1
            st.rerun()

    with col2:
        if st.button("次へ"):
            if st.session_state.q < n - 1:
                st.session_state.q += 1
                st.rerun()

    if st.session_state.q == n - 1:
        st.divider()
        if st.button("結果を見る"):
            records = []
            for i, p in enumerate(problems):
                a = st.session_state.answers.get(i, "")
                records.append({
                    "student_id": sid,
                    "question": p["question"],
                    "student_answer": a,
                    "correct_answer": str(p["answer"]),
                    "is_correct": check_answer(a, p["answer"]),
                    "timestamp": now()
                })

            df = pd.DataFrame(records)
            df.to_csv(
                RESULT_FILE,
                mode="a",
                header=not os.path.exists(RESULT_FILE),
                index=False,
                encoding="utf-8"
            )

            st.success(f"正答率：{df['is_correct'].mean()*100:.1f}%")
            st.dataframe(df)

# ==============================
# 教師画面
# ==============================
def teacher_view():
    st.header("🧑‍🏫 教師用管理")

    # --- 問題編集 ---
    st.subheader("📘 問題編集")
    problems = load_problems()

    for i, p in enumerate(problems):
        with st.expander(p["question"]):
            q = st.text_input("問題文", p["question"], key=f"q{i}")
            a = st.text_input("答え", str(p["answer"]), key=f"a{i}")

            if st.button("保存", key=f"s{i}"):
                try:
                    a_val = json.loads(a) if a.startswith("[") else a
                except:
                    a_val = a
                problems[i] = {"question": q, "answer": a_val}
                save_problems(problems)
                st.success("保存しました")
                st.rerun()

            if st.button("削除", key=f"d{i}"):
                problems.pop(i)
                save_problems(problems)
                st.rerun()

    st.subheader("➕ 新規追加")
    nq = st.text_input("問題文（新規）")
    na = st.text_input("答え（新規）")
    if st.button("追加"):
        problems.append({"question": nq, "answer": na})
        save_problems(problems)
        st.success("追加しました")
        st.rerun()

    # --- 成績 ---
    st.divider()
    st.subheader("📊 成績分析")

    if not os.path.exists(RESULT_FILE):
        st.info("成績データなし")
        return

    df = pd.read_csv(RESULT_FILE)

    st.metric("クラス正答率", f"{df['is_correct'].mean()*100:.1f}%")

    q_rate = df.groupby("question")["is_correct"].mean() * 100
    st.bar_chart(q_rate)

    sid = st.selectbox("生徒ID", df["student_id"].unique())
    sdf = df[df["student_id"] == sid]

    st.metric("個人正答率", f"{sdf['is_correct'].mean()*100:.1f}%")

    sdf["timestamp"] = pd.to_datetime(sdf["timestamp"])
    sdf = sdf.sort_values("timestamp")
    sdf["累積正答率"] = sdf["is_correct"].expanding().mean() * 100

    st.line_chart(sdf.set_index("timestamp")["累積正答率"])

    # --- 完全リセット ---
    st.divider()
    st.subheader("⚠ 完全リセット")

    if st.button("正答率・グラフ・成績を全削除"):
        if os.path.exists(RESULT_FILE):
            os.remove(RESULT_FILE)
        for k in list(st.session_state.keys()):
            if k != "mode":
                del st.session_state[k]
        st.success("完全リセット完了")
        st.rerun()

# ==============================
# メイン
# ==============================
st.set_page_config("数学学習アプリ")

if "mode" not in st.session_state:
    st.session_state.mode = None

if st.session_state.mode is None:
    st.title("📘 数学学習アプリ")
    role = st.radio("利用者", ["生徒", "教師"])

    if role == "生徒":
        if st.button("開始"):
            st.session_state.mode = "student"
            st.rerun()
    else:
        pw = st.text_input("パスワード", type="password")
        if st.button("ログイン") and pw == TEACHER_PASSWORD:
            st.session_state.mode = "teacher"
            st.rerun()

elif st.session_state.mode == "student":
    if st.button("ログアウト"):
        st.session_state.clear()
        st.rerun()
    student_view()

else:
    if st.button("ログアウト"):
        st.session_state.clear()
        st.rerun()
    teacher_view()



