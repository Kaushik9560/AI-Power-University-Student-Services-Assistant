"""Student chat and separate document administration, backed by the FastAPI contract."""
from __future__ import annotations

import json
import os
import re
from datetime import date

import requests
import streamlit as st

API = os.getenv("API_BASE_URL", "http://localhost:8000")
st.set_page_config(page_title="NSUT · Student Assistant", page_icon="🎓", layout="wide")
st.caption("NSUT · STUDENT SERVICES ASSISTANT")
st.markdown("""
<style>
 .block-container {max-width: 1160px; padding-top: 2rem; padding-bottom: 2rem;}
 .hero {padding: 8px 0 24px;}
 .eyebrow {color: #2856d8; font-size: 12px; font-weight: 700; letter-spacing: .12em;}
 .hero h1 {color: #17243b; font-size: 36px; font-weight: 750; line-height: 1.2; margin: 10px 0;}
 .hero p {color: #66738c; font-size: 16px; max-width: 700px; margin: 0;}
 [data-testid="stSidebar"] {background: #ffffff; border-right: 1px solid #e5eaf3;}
 [data-testid="stChatMessage"] {border: 1px solid #e5eaf3; border-radius: 12px;}
 [data-testid="stMetricValue"] {font-size: 25px;}
 .stButton > button {border-radius: 9px;}
 .stChatInput {border-radius: 12px;}
</style>
<div class="hero"><div class="eyebrow">NSUT · STUDENT SERVICES</div>
<h1>A clearer answer to your next question.</h1>
<p>Explore academic rules, check your demo records, and see the sources behind every answer.</p></div>
""", unsafe_allow_html=True)


def api(method: str, path: str, **kwargs):
    try:
        response = requests.request(method, f"{API}{path}", timeout=180, **kwargs)
        response.raise_for_status()
        return response.json()
    except requests.RequestException as error:
        detail = str(error)
        if getattr(error, "response", None) is not None:
            try:
                detail = str(error.response.json().get("detail", detail))
            except ValueError:
                pass
        st.error(f"The service could not complete this request. {detail}")
        return None


health = api("GET", "/health")
sources = api("GET", "/sources") or []
ready = bool(health and health["vector_store"].get("chunks", 0) > 0)
with st.sidebar:
    st.markdown("### Your demo account")
    st.caption("All student profiles, attendance, marks and CGPAs are fictional.")
    student_id = st.text_input("Demo student ID", os.getenv("DEFAULT_STUDENT_ID", "S1001")).strip().upper()
    anonymous = st.checkbox("Ask a general question", value=False, help="General policy questions do not require a student profile.")
    as_of = st.date_input("Policy date", date.today(), help="Rules are checked against this date, including future and expired notices.")
    context = ("general", as_of.isoformat()) if anonymous else (student_id, as_of.isoformat())
    if st.session_state.get("context") != context:
        st.session_state["messages"] = []
        st.session_state["context"] = context
    st.divider()
    if ready:
        st.success("Policy library ready")
    else:
        st.warning("Policy library is not ready")
    st.caption("Public NSUT policies with clearly marked synthetic demonstration notices.")
    if st.button("New conversation", use_container_width=True):
        st.session_state["messages"] = []
        st.session_state.pop("pending_question", None)
        st.rerun()

public = sum(source.get("synthetic") == "N" for source in sources)
stats = st.columns(3)
stats[0].metric("Public policy documents", public)
stats[1].metric("Synthetic student profiles", health["sqlite"].get("students", 0) if health else 0)
stats[2].metric("Demo notices", len(sources) - public)
st.caption("Educational demo · No real student data · Future demo notices are not university-issued policies")
assistant_tab, sources_tab, admin_tab = st.tabs(["Ask the assistant", "Policy library", "Document administration"])


def render_answer(result: dict):
    kind = result["answer_type"]
    labels = {"retrieved_fact": "From policy documents", "calculated": "Calculated from demo records",
              "not_found": "Information unavailable", "clarification_needed": "More detail needed",
              "refused": "Request not allowed", "conflict_flagged": "Conflicting documents"}
    st.caption(labels.get(kind, kind))
    if kind == "conflict_flagged":
        st.warning(result["answer"])
    elif kind in ("not_found", "clarification_needed", "refused"):
        st.info(result["answer"])
    else:
        st.markdown(result["answer"])
    messages = st.session_state.get("messages", [])
    latest = messages[-1].get("result", {}) if messages else {}
    if kind == "clarification_needed" and latest.get("trace_id") == result["trace_id"]:
        choices = result.get("clarification_options", [])
        if choices:
            st.caption("Choose an option, or reply in the chat below.")
            columns = st.columns(min(3, len(choices)))
            for index, choice in enumerate(choices):
                if columns[index % len(columns)].button(choice, key=f"clarify-{result['trace_id']}-{index}",
                                                        use_container_width=True):
                    st.session_state["pending_question"] = choice
    if result.get("explanation"):
        if kind == "calculated":
            st.markdown("**Explanation**")
        st.markdown(result["explanation"])
    if result.get("assumptions"):
        st.markdown("**What this scenario assumes**")
        for assumption in result["assumptions"]:
            st.markdown(f"- {assumption}")
    citations = result.get("citations", [])
    if citations:
        with st.expander(f"View {len(citations)} supporting source(s)", expanded=True):
            for index, citation in enumerate(citations, 1):
                label = citation.get("label") or f"[S{index}]"
                st.markdown(f"**{label} {citation['title']}**")
                details = [f"Version {citation.get('version') or 'unspecified'}",
                           f"Effective date: {citation.get('effective_from') or 'not specified by publisher'}"]
                if citation.get("section"):
                    number = re.match(r"^\d+(?:\.\d+)*", str(citation["section"]))
                    details.insert(0, f"Clause {number.group() if number else citation['section']}")
                if citation.get("page"):
                    details.insert(0, f"PDF page {citation['page']}")
                st.caption(" · ".join(details))
                if citation.get("excerpt"):
                    st.markdown(f"> {citation['excerpt'].replace(chr(10), ' ')}")
                source = next((row for row in sources if row["doc_id"] == citation["doc_id"]), None)
                if source and str(source.get("provenance", "")).startswith(("https://", "http://")):
                    st.link_button("Open original document", source["provenance"])
    with st.expander("How this answer was checked"):
        st.caption(f"Trace {result['trace_id']} · Policy date {result['as_of_date']} · {result.get('latency_ms', 0)} ms")
        if result.get("applied_rules"):
            st.dataframe(result["applied_rules"], hide_index=True, use_container_width=True)
        for tool in result.get("tools_invoked", []):
            st.markdown(f"**{tool['tool']}** · {tool['status']}")
            st.json({"input": tool.get("input"), "output": tool.get("output")}, expanded=False)
        for conflict in result.get("conflicts_detected", []):
            st.caption(conflict["note"])
        if st.button("Load audit record", key="audit-" + result["trace_id"]):
            record = api("GET", "/audit/" + result["trace_id"])
            if record:
                st.json(record, expanded=False)


with assistant_tab:
    if not ready:
        st.error("The policy library is empty or unavailable. Start the project with scripts/run_local.py and check the API startup log.")
    examples = ["What is the minimum attendance required for end-semester exams?",
                "What is my attendance in DBMS?", "Does NSUT provide supplementary examinations?"]
    if not st.session_state.get("messages"):
        st.markdown("**Start with a question**")
        for column, label, question in zip(st.columns(3), ["Attendance rules", "My DBMS attendance", "Supplementary exams"], examples):
            if column.button(label, use_container_width=True, disabled=not ready):
                st.session_state["pending_question"] = question
        st.caption("You can also ask about scholarship rules, failed courses, or attendance scenarios.")
    for message in st.session_state.get("messages", []):
        with st.chat_message(message["role"]):
            if message["role"] == "user":
                st.markdown(message["text"])
            else:
                render_answer(message["result"])
    typed = st.chat_input("Ask about university rules or your demo records…", disabled=not ready)
    question = typed or st.session_state.pop("pending_question", None)
    if question:
        headers = {} if anonymous else {"X-Student-Id": student_id}
        payload = {"question": question, "as_of_date": as_of.isoformat()}
        messages = st.session_state.get("messages", [])
        if messages and messages[-1]["role"] == "assistant":
            payload["previous_trace_id"] = messages[-1]["result"]["trace_id"]
        with st.spinner("Checking the relevant policies and records…"):
            result = api("POST", "/ask", json=payload, headers=headers)
        if result:
            st.session_state.setdefault("messages", []).extend([
                {"role": "user", "text": question}, {"role": "assistant", "result": result}])
            st.rerun()

with sources_tab:
    st.markdown("### Know where the answer comes from")
    st.caption("Public originals and synthetic demonstration notices are identified by provenance.")
    if sources:
        rows = [{"Document": source["title"], "Type": "Public source" if source.get("synthetic") == "N" else "Synthetic demo",
                 "Version": source["version"], "Effective from": source.get("effective_from") or "Not specified",
                 "Authority": source["authority_level"]} for source in sources]
        st.dataframe(rows, hide_index=True, use_container_width=True)
        for source in sources:
            with st.expander(source["title"]):
                st.caption(f"{source['doc_id']} · Issuer: {source['issuer']} · Retrieved: {source.get('retrieved_on', '')}")
                st.write("Programme scope:", source.get("scope_programmes", "ALL"))
                st.write("Batch scope:", source.get("scope_batches", "ALL"))
                st.write("Supersedes:", source.get("supersedes") or "None declared")
                st.write("Provenance:", source.get("provenance") or "Not supplied")

with admin_tab:
    st.markdown("### Add a policy document")
    st.caption("Use public official policies or clearly labelled synthetic test notices. Exclude real student rosters, marks and personal records.")
    # Reactive widgets clear stale validation as the user fills missing values.
    # Explicit keys retain the uploaded file and metadata through ordinary reruns.
    with st.container(border=True):
        uploaded = st.file_uploader("Policy file", type=["md", "txt", "pdf"], key="ingest-file")
        left, right = st.columns(2)
        doc_id = left.text_input("Document ID", placeholder="NSUT-CIRCULAR-2026-01", key="ingest-id")
        title = right.text_input("Document title", key="ingest-title")
        issuer = left.text_input("Issuing office", key="ingest-issuer")
        doc_type = right.selectbox("Document type", ["circular", "regulation", "notice", "handbook", "faq", "unofficial"], key="ingest-type")
        authority = left.selectbox("Authority level", [1, 2, 3, 4, 5], index=1,
                                   format_func=lambda level: {1: "1 · Regulations / ordinances", 2: "2 · Authorised circulars", 3: "3 · Department notices", 4: "4 · Handbooks / FAQs", 5: "5 · Unofficial information"}[level], key="ingest-authority")
        version = right.text_input("Version", "1.0", key="ingest-version")
        effective_from = left.text_input("Effective from (YYYY-MM-DD)", help="Leave blank only if the publisher does not specify a date.", key="ingest-from")
        effective_to = right.text_input("Effective until (optional)", key="ingest-until")
        programmes = left.text_input("Programme scope", "ALL", key="ingest-programmes")
        batches = right.text_input("Batch scope", "ALL", key="ingest-batches")
        supersedes = st.text_input("Document or clause replaced (optional)", placeholder="NSUT-BTECH-2019#11.2", key="ingest-supersedes")
        provenance = st.text_input("Original URL or provenance", key="ingest-provenance")
        synthetic = st.checkbox("This is a synthetic demonstration document", key="ingest-synthetic")
        missing = [label for label, present in (("Policy file", uploaded is not None),
                   ("Document ID", bool(doc_id.strip())), ("Document title", bool(title.strip())),
                   ("Issuing office", bool(issuer.strip()))) if not present]
        if missing:
            st.caption("Required before adding: " + ", ".join(missing))
        submitted = st.button("Add to policy library", type="primary", disabled=bool(missing), key="ingest-submit")
    if submitted:
        if missing:
            st.error("Missing: " + ", ".join(missing))
        else:
            metadata = dict(doc_id=doc_id.strip(), title=title.strip(), issuer=issuer.strip(), doc_type=doc_type,
                            authority_level=authority, version=version, effective_from=effective_from,
                            effective_to=effective_to, scope_programmes=programmes, scope_batches=batches,
                            supersedes=supersedes, provenance=provenance, retrieved_on=date.today().isoformat(),
                            synthetic="Y" if synthetic else "N")
            with st.spinner("Reading, indexing and registering the document…"):
                result = api("POST", "/ingest", files={"file": (uploaded.name, uploaded.getvalue())},
                             data={"metadata": json.dumps(metadata)})
            if result:
                st.session_state["ingest-result"] = result
                st.rerun()
    if st.session_state.get("ingest-result"):
        result = st.session_state["ingest-result"]
        st.success(f"Last added: {result['doc_id']} · {result['chunks_indexed']} searchable chunks · {len(result.get('rules_registered', []))} explicit attendance rules registered.")
        st.caption("Choose New conversation to ask against the updated library.")
    if health:
        with st.expander("Service diagnostics"):
            st.json(health, expanded=True)
