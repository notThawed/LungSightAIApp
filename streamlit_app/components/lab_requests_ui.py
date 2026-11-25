"""Laboratory requests UI for physician and staff follow-up views.

Physician examination is itself an st.dialog. For physician previews the
parent page must pass on_view_result and render show_lab_result_dialog at
page level, not from within the examination dialog.
"""
from __future__ import annotations

from html import escape
from pathlib import Path

import streamlit as st

from backend.backend_utils.lab_request_utils import (
    TEST_OPTIONS,
    get_requests_for_examination,
    get_requests_for_follow_up,
    upload_lab_document,
    signed_lab_document_url,
    delete_lab_document,
)

CSS_PATH = (
    Path(__file__).resolve().parents[2]
    / "shared" / "theme" / "css_content" / "lab_requests.css"
)


def _css():
    if CSS_PATH.is_file():
        st.markdown(
            "<style>" + CSS_PATH.read_text(encoding="utf-8") + "</style>",
            unsafe_allow_html=True,
        )
    st.markdown("""
    <style>
    .lr-clean-card {border:1px solid #dce6ef;border-radius:12px;
        background:#f8fbfd;padding:15px 18px;margin:12px 0 7px;}
    .lr-clean-title {font-size:14px;font-weight:700;color:#173c55;}
    .lr-clean-meta {font-size:12px;color:#657b8e;margin-top:4px;}
    </style>
    """, unsafe_allow_html=True)


def lab_request_selector(examination_id, actor_id, key_prefix):
    _css()
    st.markdown(
        '<div class="lr-heading"><span class="material-symbols-rounded">'
        'biotech</span><b>Laboratory Requests</b></div>',
        unsafe_allow_html=True,
    )
    try:
        saved = get_requests_for_examination(examination_id, actor_id)
        default = [r["test_type"] for r in saved if r.get("status") != "Cancelled"]
    except Exception as exc:
        st.error(f"Cannot load laboratory requests: {exc}")
        return None

    options = list(TEST_OPTIONS)
    for test in default:
        if test not in options:
            options.append(test)
    chosen = st.multiselect(
        "Types of laboratory requests", options, default=default,
        key=f"{key_prefix}_lab_types",
    )
    other = st.text_input(
        "Other laboratory request (optional)",
        key=f"{key_prefix}_lab_other", max_chars=120,
        placeholder="Specify a test not in the list",
    ).strip()
    if other and other not in chosen:
        chosen.append(other)
    st.caption(
        "Selected tests are saved individually. Results can be uploaded "
        "from the associated follow-up appointment."
    )
    return chosen


def _document_type(doc):
    content_type = str(doc.get("content_type") or "").lower()
    filename = str(doc.get("original_filename") or "").lower()
    if content_type == "application/pdf" or filename.endswith(".pdf"):
        return "pdf"
    if content_type.startswith("image/") or filename.endswith(
        (".png", ".jpg", ".jpeg", ".webp")
    ):
        return "image"
    return "other"


@st.dialog("Laboratory Result", width="large")
def show_lab_result_dialog(
    follow_up_id,
    lab_request_id,
    actor_id,
    allow_upload=False,
    key_prefix="lab",
    on_back=None,
):
    """A TOP-LEVEL result dialog; physician's parent page must call this."""
    _css()
    try:
        orders = get_requests_for_follow_up(follow_up_id, actor_id)
        order = next(
            (r for r in orders if str(r["lab_request_id"]) == str(lab_request_id)),
            None,
        )
    except Exception as exc:
        st.error(f"Unable to load laboratory result: {exc}")
        if on_back and st.button("Back to Examination"):
            on_back()
        return

    if order is None:
        st.warning("This laboratory request is no longer available.")
        if on_back and st.button("Back to Examination"):
            on_back()
        return

    test_type = str(order.get("test_type") or "Laboratory Test")
    st.markdown(f"### {escape(test_type)}")
    documents = order.get("documents") or []
    if not documents:
        st.info("No result documents have been uploaded.")
    else:
        doc_map = {str(doc["document_id"]): doc for doc in documents}
        selector_key = f"{key_prefix}_preview_select_{lab_request_id}"
        # A deleted document may still be selected in widget state.
        if (selector_key in st.session_state
                and st.session_state[selector_key] not in doc_map):
            st.session_state.pop(selector_key, None)

        def _label(document_id):
            doc = doc_map[document_id]
            filename = str(doc.get("original_filename") or "Result")
            uploaded = str(doc.get("uploaded_at") or "")[:16].replace("T", " ")
            return f"{filename} — {uploaded}"

        selected_id = st.selectbox(
            "Select a document to preview", list(doc_map),
            format_func=_label, key=selector_key,
        )
        doc = doc_map[selected_id]
        filename = str(doc.get("original_filename") or "Result")
        st.caption(filename)
        try:
            url = signed_lab_document_url(selected_id, actor_id)
        except Exception as exc:
            st.error(f"Cannot access result: {exc}")
            url = None

        if url:
            kind = _document_type(doc)
            if kind == "image":
                st.image(url, caption=filename, use_container_width=True)
            elif kind == "pdf":
                # Browser/storage policy may prevent embedding; fallback below.
                st.components.v1.html(
                    f'<iframe src="{escape(url, quote=True)}" '
                    'style="width:100%;height:520px;border:1px solid #dce6ef;'
                    'border-radius:8px" title="PDF laboratory result"></iframe>',
                    height=540,
                )
            else:
                st.info("Inline preview is unavailable for this file type.")

            st.link_button(
                "Open Original File", url, icon=":material/open_in_new:"
            )
        else:
            st.warning("A document preview link is unavailable.")

        if allow_upload:
            confirm_key = f"{key_prefix}_confirm_delete_{selected_id}"
            if st.button(
                "Delete File", icon=":material/delete:",
                key=f"{key_prefix}_delete_{selected_id}",
            ):
                st.session_state[confirm_key] = True

            if st.session_state.get(confirm_key):
                st.warning(f"Permanently delete '{filename}'?")
                yes, no = st.columns(2)
                if yes.button(
                    "Confirm Delete", type="primary",
                    key=f"{key_prefix}_yes_{selected_id}",
                ):
                    try:
                        delete_lab_document(selected_id, follow_up_id, actor_id)
                    except Exception as exc:
                        st.error(f"Unable to delete result: {exc}")
                    else:
                        st.session_state.pop(confirm_key, None)
                        st.session_state.pop(selector_key, None)
                        st.session_state[
                            f"{key_prefix}_delete_success_{follow_up_id}"
                        ] = f"Deleted '{filename}' successfully."
                        st.rerun()
                if no.button("Cancel", key=f"{key_prefix}_no_{selected_id}"):
                    st.session_state.pop(confirm_key, None)
                    st.rerun()

    if on_back:
        st.divider()
        if st.button(
            "Back to Examination", icon=":material/arrow_back:",
            key=f"{key_prefix}_back_to_exam_{lab_request_id}",
            use_container_width=True,
        ):
            on_back()
    else:
        st.caption("Close this dialog using the X at the top right.")


def render_follow_up_lab_documents(
    follow_up_id,
    actor_id,
    allow_upload=False,
    key_prefix="lab",
    on_view_result=None,
):
    """Staff uses a local dialog; physician uses the page-level callback."""
    _css()
    for action in ("upload", "delete"):
        message = st.session_state.pop(
            f"{key_prefix}_{action}_success_{follow_up_id}", None
        )
        if message:
            st.success(message)

    st.markdown(
        '<div class="lr-heading"><span class="material-symbols-rounded">'
        'science</span><b>Laboratory Requests &amp; Results</b></div>',
        unsafe_allow_html=True,
    )
    try:
        orders = get_requests_for_follow_up(follow_up_id, actor_id)
    except Exception as exc:
        st.error(f"Cannot load laboratory requests: {exc}")
        return
    if not orders:
        st.caption("No laboratory tests were requested for this follow-up.")
        return

    for order in orders:
        request_id = str(order["lab_request_id"])
        test_type = str(order.get("test_type") or "Laboratory Test")
        documents = order.get("documents") or []
        has_results = bool(documents)
        status = (
            f"Result Uploaded · {len(documents)} file(s)"
            if has_results else "Awaiting Result"
        )
        st.markdown(
            '<div class="lr-clean-card">'
            f'<div class="lr-clean-title">{escape(test_type)}</div>'
            f'<div class="lr-clean-meta">{escape(status)}</div>'
            '</div>',
            unsafe_allow_html=True,
        )

        if has_results:
            if st.button(
                "View Result", icon=":material/visibility:",
                key=f"{key_prefix}_view_result_{request_id}",
            ):
                if on_view_result is not None:
                    # Physician: callback switches dialogs at the page level.
                    on_view_result(request_id)
                elif allow_upload:
                    # Staff: this page is not already inside a dialog.
                    show_lab_result_dialog(
                        follow_up_id, request_id, actor_id,
                        allow_upload=True, key_prefix=key_prefix,
                    )
                else:
                    st.warning(
                        "This preview is inside another dialog. "
                        "The parent page must provide on_view_result."
                    )
            continue

        if not allow_upload:
            st.caption("The laboratory result has not been uploaded yet.")
            continue

        version_key = f"{key_prefix}_upload_version_{follow_up_id}_{request_id}"
        version = st.session_state.get(version_key, 0)
        upload = st.file_uploader(
            f"Upload result — {test_type}",
            type=["pdf", "png", "jpg", "jpeg"],
            key=f"{key_prefix}_upload_{follow_up_id}_{request_id}_{version}",
            help="PDF, PNG, or JPG, maximum 10 MB.",
        )
        if st.button(
            "Save Laboratory Result", icon=":material/upload_file:",
            key=f"{key_prefix}_save_{follow_up_id}_{request_id}",
            disabled=upload is None,
        ):
            try:
                upload_lab_document(
                    request_id, follow_up_id, actor_id,
                    upload.name, upload.getvalue(),
                )
            except Exception as exc:
                st.error(f"Unable to upload laboratory result: {exc}")
            else:
                st.session_state[version_key] = version + 1
                st.session_state[
                    f"{key_prefix}_upload_success_{follow_up_id}"
                ] = f"{test_type} result uploaded successfully."
                st.rerun()
