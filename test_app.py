import streamlit as st
import json
import random
import pandas as pd
import numpy as np
import sympy as sp
import os
import unicodedata
import time
from datetime import datetime
import glob

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
# 2. データ管理ロジック (強化版)
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
    """CSVからデータを確実に読み込むロジック"""
    path = get_result_file()
    if not os.path.exists(path):
        return pd.DataFrame(columns=REQUIRED_COLUMNS)
    try:
        # engine='python'でファイルロックの影響を抑え、UTF-8-SIGでExcel対応
        df = pd.read_csv(path, encoding='utf-8-sig', engine='python')
        if df.empty:
            return pd.DataFrame(columns=REQUIRED_COLUMNS)
        if "is_correct" in df.columns:
            df["is_correct"] = pd.to_numeric(df["is_correct"], errors='coerce').fillna(0)
        return df
    except Exception:
        return pd.DataFrame(columns=REQUIRED_COLUMNS)

def safe_save_results(new_df, path):
    """保存のリトライとエラーハンドリング"""
    max_retries = 3
    for i in range(max_retries):
        try:
            header = not os.path.exists(path)
            # 追記モード('a')、インデックスなし、BOM付きUTF-8で保存
            new_df.to_csv(path, mode='a', index=False, header=header, encoding='utf-8-sig')
            return True
        except Exception:
            time.sleep(0.2)
    return False

# --- 採点ロジック ---
def normalize_text(s):
    if not isinstance(s, str): return str(s)
    # 全角半角・空白・大文字小文字の揺れを吸収
    s = unicodedata.normalize("NFKC", s).strip().replace(" ", "")
    s = s.replace("，", ",").replace("√", "sqrt").replace("π", "pi")
    return s

def is_equal(student, correct):
    s_raw = normalize_text(student)
    c_raw = normalize_text(correct)
    if s_raw == c_raw: return True
    # 数値としての比較
    try:
        if abs(float(s_raw) - float(c_raw)) < 1e-7: return True
    except: pass
    # Sympyによる数式比較
    try:
        s_expr = s_raw.replace("x=", "").replace("y=", "")
        c_expr = c_raw.replace("x=", "").replace("y=", "")
        if sp.simplify(f"({s_expr}) - ({c_expr})") == 0: return True
    except: pass
    return False

# ==============================
# 3. 生徒用画面 (結果表示機能付き)
# ==============================

def student_view():
    subject = st.session_state.selected_subject
    st.header(f"✏️ {subject} テスト")
    
    # セッション状態の初期化
    if "q_idx" not in st.session_state:
        st.session_state.q_idx = 0
        st.session_state.current_results = []
        st.session_state.done = False

    # ID入力
    if "student_id" not in st.session_state or not st.session_state.student_id:
        sid = st.text_input("生徒ID（氏名や出席番号）を入力してください")
        if st.button("テストを開始"):
            if sid:
                st.session_state.student_id = sid
                st.rerun()
            else:
                st.warning("IDを入力してください")
        return

    problems = load_problems()
    if not problems:
        st.warning(f"{subject}の問題はまだ登録されていません。")
        return

    # --- テスト完了後の結果表示画面 ---
    if st.session_state.done:
        st.balloons()
        st.success(f"提出完了！お疲れ様でした、{st.session_state.student_id}さん！")
        
        results = st.session_state.current_results
        score = sum([r["is_correct"] for r in results])
        total = len(results)
        percent = int(score/total*100) if total > 0 else 0
        
        c1, c2 = st.columns(2)
        c1.metric("得点", f"{score} / {total}")
        c2.metric("正答率", f"{percent}%")

        st.subheader("📝 あなたの解答と正解")
        for i, r in enumerate(results):
            icon = "✅" if r["is_correct"] else "❌"
            with st.expander(f"問 {i+1}: {icon} {'正解' if r['is_correct'] else '不正解'}"):
                st.write(f"**問題:** {r['question']}")
                st.write(f"**あなたの回答:** {r['student_answer']}")
                if not r["is_correct"]:
                    st.write(f"**正しい答え:** :green[{r['correct_answer']}]")
        
        if st.button("ホーム（教科選択）に戻る"):
            for key in ["q_idx", "current_results", "done", "student_id"]:
                if key in st.session_state: del st.session_state[key]
            st.session_state.mode = None
            st.rerun()
        return

    # --- 出題中画面 ---
    prob = problems[st.session_state.q_idx]
    st.progress((st.session_state.q_idx) / len(problems))
    st.subheader(f"問題 {st.session_state.q_idx + 1} / {len(problems)}")
    
    if "$" in prob["question"]:
        st.latex(prob["question"].replace("$", ""))
    else:
        st.info(prob["question"])
    
    q_type = prob.get("type", "記述式")
    if q_type == "選択式":
        ans = st.radio("答えを選んでください", prob.get("options", []), key=f"q_{st.session_state.q_idx}")
    else:
        ans = st.text_input("答えを入力してください", key=f"q_{st.session_state.q_idx}")

    btn_label = "次の問題へ" if st.session_state.q_idx < len(problems)-1 else "採点して終了"
    if st.button(btn_label):
        is_c = 1 if is_equal(ans, prob["answer"]) else 0
        
        res_entry = {
            "student_id": st.session_state.student_id, 
            "question": prob["question"],
            "student_answer": ans, 
            "correct_answer": prob["answer"],
            "is_correct": is_c, 
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M"),
            "type": q_type
        }
        
        # 1問解くごとに即座にCSVに保存する（重要：これで消えなくなります）
        st.session_state.current_results.append(res_entry)
        safe_save_results(pd.DataFrame([res_entry]), get_result_file())
        
        if st.session_state.q_idx < len(problems) - 1:
            st.session_state.q_idx += 1
            st.rerun()
        else:
            st.session_state.done = True
            st.rerun()

# ==============================
# 4. 教師用画面
# ==============================

def teacher_view():
    subject = st.session_state.selected_subject
    st.header(f"🧑‍🏫 管理画面（{subject}）")
    tab1, tab2, tab3 = st.tabs(["📊 成績分析", "📝 問題編集", "⚙️ データ管理"])

    with tab1:
        df = load_results()
        if not df.empty:
            st.subheader("全体データログ")
            st.dataframe(df.sort_values("timestamp", ascending=False), use_container_width=True)
            
            st.divider()
            st.subheader("👤 生徒別平均正答率")
            # 0点の生徒も含めて集計
            stats = df.groupby("student_id")["is_correct"].mean() * 100
            st.bar_chart(stats)
            
            # 全体平均
            avg_all = df["is_correct"].mean() * 100
            st.metric("クラス全体平均正答率", f"{avg_all:.1f}%")
        else:
            st.info(f"まだ {subject} の解答データがありません。")

    with tab2:
        problems = load_problems()
        st.subheader("➕ 問題の登録")
        q_type = st.selectbox("問題形式", ["記述式", "選択式"])
        nq = st.text_area("問題文（数式は $x^2$ など）")
        
        options = []
        if q_type == "選択式":
            c1, c2, c3, c4 = st.columns(4)
            o1 = c1.text_input("選択肢A")
            o2 = c2.text_input("選択肢B")
            o3 = c3.text_input("選択肢C")
            o4 = c4.text_input("選択肢D")
            options = [o for o in [o1, o2, o3, o4] if o]
            na = st.selectbox("正解となる選択肢", options) if options else ""
        else:
            na = st.text_input("正解の答え")

        if st.button("問題を保存"):
            if nq and na:
                new_p = {"type": q_type, "question": nq, "answer": na, "options": options}
                problems.append(new_p)
                save_problems(problems)
                st.success("問題を登録しました。")
                st.rerun()

        st.divider()
        st.subheader("登録済みの問題一覧")
        for i, p in enumerate(problems):
            with st.expander(f"問{i+1}: {p['question'][:30]}"):
                st.write(f"形式: {p.get('type')}")
                st.write(f"正解: {p['answer']}")
                if st.button("削除", key=f"del_{i}"):
                    problems.pop(i)
                    save_problems(problems)
                    st.rerun()

    with tab3:
        st.subheader("データのアーカイブ・リセット")
        if st.button("📁 現在のデータを保存して新規開始"):
            path = get_result_file()
            if os.path.exists(path):
                ts = datetime.now().strftime("%Y%m%d_%H%M")
                os.rename(path, path.replace(".csv", f"_{ts}.csv"))
                st.success("これまでのデータをアーカイブしました。")
                st.rerun()

# ==============================
# 5. メイン制御
# ==============================
st.set_page_config(page_title="学習分析システム", layout="wide")

if "mode" not in st.session_state: st.session_state.mode = None
if "selected_subject" not in st.session_state: st.session_state.selected_subject = "数学"

# サイドバーメニュー
with st.sidebar:
    st.title("🍀 Menu")
    if st.button("🏠 教科選びに戻る"):
        for k in ["q_idx", "current_results", "done", "student_id", "mode"]:
            if k in st.session_state: del st.session_state[k]
        st.session_state.mode = None
        st.rerun()
    
    st.divider()
    st.write(f"教科: **{st.session_state.selected_subject}**")
    
    if st.button("✏️ テストを受ける"):
        st.session_state.mode = "student"
        st.rerun()
    
    if st.button("🧑‍🏫 教師用管理画面"):
        st.session_state.mode = "auth"
        st.rerun()

# メイン表示
if st.session_state.mode is None:
    st.title("📚 学習分析システム")
    st.write("まず、学習する教科を選んでください。")
    cols = st.columns(len(SUBJECTS))
    for i, sub in enumerate(SUBJECTS):
        if cols[i].button(sub, use_container_width=True):
            st.session_state.selected_subject = sub
            # 教科変更時に状態リセット
            for k in ["q_idx", "current_results", "done", "student_id"]:
                if k in st.session_state: del st.session_state[k]
            st.success(f"**{sub}** を選択しました。左メニューから開始してください。")

elif st.session_state.mode == "student":
    student_view()

elif st.session_state.mode == "auth":
    st.subheader("教師用ログイン")
    pw = st.text_input("パスワード", type="password")
    if st.button("ログイン"):
        if pw == TEACHER_PASSWORD:
            st.session_state.mode = "teacher"
            st.rerun()
        else:
            st.error("パスワードが違います")

elif st.session_state.mode == "teacher":
    teacher_view()