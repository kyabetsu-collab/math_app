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
        if not df.empty and "is_correct" in df.columns:
            df["is_correct"] = pd.to_numeric(df["is_correct"], errors='coerce').fillna(0).astype(int)
        return df
    except:
        return pd.DataFrame(columns=REQUIRED_COLUMNS)

def save_all_results(df):
    """データフレームを丸ごと保存（削除反映用）"""
    path = get_result_file()
    df.to_csv(path, index=False, encoding='utf-8-sig')

def save_final_results(results_list):
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
        s_expr = s_raw.replace("x=", "").replace("y=", "")
        c_expr = c_raw.replace("x=", "").replace("y=", "")
        if sp.simplify(f"({s_expr}) - ({c_expr})") == 0: return True
    except: pass
    return False

# ==============================
# 3. 生徒用画面
# ==============================

def student_view():
    subject = st.session_state.selected_subject
    st.header(f"✏️ {subject} テスト")
    
    problems = load_problems()
    if not problems:
        st.warning("問題が登録されていません。")
        return

    if "q_idx" not in st.session_state:
        st.session_state.q_idx = 0
        st.session_state.answers = [""] * len(problems)
        st.session_state.done = False

    if "student_id" not in st.session_state:
        st.subheader("ログイン")
        sid = st.text_input("名前（または生徒ID）を入力してください")
        if st.button("テストを開始"):
            if sid:
                st.session_state.student_id = sid
                st.rerun()
            else: st.warning("IDを入力してください")
        return

    if st.session_state.done:
        st.balloons()
        st.success(f"提出完了！ {st.session_state.student_id}さん、お疲れ様でした。")
        
        score = 0
        for i, prob in enumerate(problems):
            if is_equal(st.session_state.answers[i], prob["answer"]): score += 1
        
        st.metric("今回の得点", f"{score} / {len(problems)}")
        
        with st.expander("🔍 解答の確認と答え合わせ"):
            for i, prob in enumerate(problems):
                ans = st.session_state.answers[i]
                correct = is_equal(ans, prob["answer"])
                st.write(f"**問 {i+1}: {'✅正解' if correct else '❌不正解'}**")
                st.write(f"問題: {prob['question']}")
                st.write(f"あなたの答え: {ans}")
                st.write(f"正しい答え: {prob['answer']}")
                st.divider()

        if st.button("完了して戻る"):
            for k in ["q_idx", "answers", "done", "student_id"]:
                if k in st.session_state: del st.session_state[k]
            st.session_state.mode = None
            st.rerun()
        return

    idx = st.session_state.q_idx
    prob = problems[idx]
    st.subheader(f"問題 {idx + 1} / {len(problems)}")
    st.info(prob["question"])
    
    q_type = prob.get("type", "記述式")
    if q_type == "選択式":
        opts = prob.get("options", [])
        d_idx = opts.index(st.session_state.answers[idx]) if st.session_state.answers[idx] in opts else 0
        ans = st.radio("答え", opts, index=d_idx, key=f"a_{idx}")
    else:
        ans = st.text_input("答えを入力", value=st.session_state.answers[idx], key=f"a_{idx}")

    st.session_state.answers[idx] = ans

    c1, c2, c3 = st.columns([1,1,2])
    with c1:
        if idx > 0 and st.button("⬅️ 戻る"):
            st.session_state.q_idx -= 1
            st.rerun()
    with c2:
        if idx < len(problems) - 1 and st.button("次へ ➡️"):
            st.session_state.q_idx += 1
            st.rerun()
    with c3:
        if st.button("📝 終了して提出"):
            ts = datetime.now().strftime("%Y-%m-%d %H:%M")
            records = [{"student_id": st.session_state.student_id, "question": p["question"], "student_answer": st.session_state.answers[i], "correct_answer": p["answer"], "is_correct": 1 if is_equal(st.session_state.answers[i], p["answer"]) else 0, "timestamp": ts, "type": p.get("type", "記述式")} for i, p in enumerate(problems)]
            save_final_results(records)
            st.session_state.done = True
            st.rerun()

# ==============================
# 4. 教師用画面 (Excel保存・削除機能追加)
# ==============================

def teacher_view():
    subject = st.session_state.selected_subject
    st.header(f"🧑‍🏫 {subject} 管理ダッシュボード")
    tab1, tab2, tab3 = st.tabs(["📊 成績分析・保存", "📝 問題編集", "⚙️ データ管理"])

    with tab1:
        df = load_results()
        if not df.empty:
            # --- 保存機能 ---
            st.subheader("💾 成績データの保存")
            
            # 生徒別の正答率まとめ
            student_summary = df.groupby("student_id")["is_correct"].mean() * 100
            student_summary = student_summary.reset_index().rename(columns={"is_correct": "正答率(%)"})
            
            col_d1, col_d2 = st.columns(2)
            # 全解答データのCSV
            csv_raw = df.to_csv(index=False, encoding='utf-8-sig').encode('utf-8-sig')
            col_d1.download_button("📂 全解答データをCSVで保存", data=csv_raw, file_name=f"{subject}_raw_data.csv", mime="text/csv")
            
            # 生徒別正答率のCSV
            csv_summary = student_summary.to_csv(index=False, encoding='utf-8-sig').encode('utf-8-sig')
            col_d2.download_button("🥇 生徒別正答率を保存", data=csv_summary, file_name=f"{subject}_score_summary.csv", mime="text/csv")

            st.divider()
            
            # --- 分析表示 ---
            st.subheader("📈 理解度分析")
            c1, c2 = st.columns(2)
            c1.metric("全体平均", f"{(df['is_correct'].mean()*100):.1f}%")
            c2.metric("受験人数", f"{df['student_id'].nunique()}人")
            
            q_avg = df.groupby("question")["is_correct"].mean() * 100
            st.bar_chart(q_avg)

            st.divider()
            
            # --- 削除機能 ---
            st.subheader("🗑️ データの個別削除")
            st.write("誤って送信されたデータや、テストデータを選択して削除できます。")
            
            # 削除対象の選択
            target_sid = st.selectbox("削除したい生徒名を選択", ["-- 選択してください --"] + sorted(df["student_id"].unique()))
            if target_sid != "-- 選択してください --":
                target_df = df[df["student_id"] == target_sid]
                st.write(f"選択された生徒: {target_sid} (全 {len(target_df)} 件の解答)")
                if st.button(f"🔴 {target_sid} さんの全解答を削除する"):
                    new_df = df[df["student_id"] != target_sid]
                    save_all_results(new_df)
                    st.success(f"{target_sid} さんのデータを削除しました。")
                    st.rerun()
        else:
            st.info("解答データがありません。")

    with tab2:
        problems = load_problems()
        with st.form("add_q"):
            st.write("### 問題の追加")
            qt = st.selectbox("形式", ["記述式", "選択式"])
            qq = st.text_area("問題文")
            qa = st.text_input("正解")
            opts = st.text_input("選択肢（選択式のみ・カンマ区切り）")
            if st.form_submit_button("保存"):
                problems.append({"type": qt, "question": qq, "answer": qa, "options": [o.strip() for o in opts.split(",")] if opts else []})
                save_problems(problems)
                st.rerun()
        
        for i, p in enumerate(problems):
            with st.expander(f"問 {i+1}: {p['question'][:20]}"):
                if st.button(f"この問題を削除", key=f"del_p_{i}"):
                    problems.pop(i)
                    save_problems(problems)
                    st.rerun()

    with tab3:
        if st.button("⚠️ 全ての成績データを消去"):
            path = get_result_file()
            if os.path.exists(path):
                os.remove(path)
                st.success("全てのデータをリセットしました。")
                st.rerun()

# ==============================
# 5. メイン制御
# ==============================
st.set_page_config(page_title="学習分析システム・完全版", layout="wide")
if "mode" not in st.session_state: st.session_state.mode = None
if "selected_subject" not in st.session_state: st.session_state.selected_subject = "数学"

with st.sidebar:
    st.title("🍀 メニュー")
    if st.button("🏠 教科選択へ戻る"):
        for k in ["q_idx", "answers", "done", "student_id", "mode"]:
            if k in st.session_state: del st.session_state[k]
        st.session_state.mode = None; st.rerun()
    st.divider()
    if st.button("✏️ テストを受ける"): st.session_state.mode = "student"; st.rerun()
    if st.button("🧑‍🏫 教師用画面"): st.session_state.mode = "auth"; st.rerun()

if st.session_state.mode is None:
    st.title("📚 学習分析システム")
    cols = st.columns(len(SUBJECTS))
    for i, sub in enumerate(SUBJECTS):
        if cols[i].button(sub, use_container_width=True):
            st.session_state.selected_subject = sub; st.rerun()
elif st.session_state.mode == "student": student_view()
elif st.session_state.mode == "auth":
    pw = st.text_input("パスワード", type="password")
    if st.button("ログイン"):
        if pw == TEACHER_PASSWORD: st.session_state.mode = "teacher"; st.rerun()
elif st.session_state.mode == "teacher": teacher_view()