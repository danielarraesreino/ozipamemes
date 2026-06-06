"""
Dashboard Streamlit — OzielMemes Pipeline
Cidadania Conectada: Vozes do Oziel
"""
from __future__ import annotations

import io
import json
import os
import subprocess
import sys
import zipfile
from pathlib import Path

import streamlit as st

ROOT = Path(__file__).parent
sys.path.insert(0, str(ROOT))

st.set_page_config(
    page_title="OzielMemes Pipeline",
    page_icon="🎮",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── DB e cache ────────────────────────────────────────────────────────────────

@st.cache_resource
def get_db():
    from config import get_config
    from database.factory import get_db as _get_db
    config = get_config()
    db = _get_db(config)
    db.init_db()
    return db

@st.cache_data(ttl=8)
def load_stats():
    db = get_db()
    return db.count_memes(), db.get_queue_stats()

@st.cache_data(ttl=8)
def load_memes():
    db = get_db()
    return db.list_memes()

@st.cache_data(ttl=8)
def load_conteudo(meme_id):
    return get_db().get_conteudo_atual(meme_id)

@st.cache_data(ttl=8)
def load_verificacao(meme_id):
    return get_db().get_verificacao_atual(meme_id)

@st.cache_data(ttl=8)
def load_data_points(meme_id):
    return get_db().get_data_points(meme_id)

@st.cache_data(ttl=8)
def load_fila(estado):
    return get_db().get_queue_by_estado(estado, limit=200)

def run_cmd(args):
    r = subprocess.run(
        [sys.executable, str(ROOT / "run.py")] + args,
        capture_output=True, text=True, cwd=str(ROOT)
    )
    return r.stdout + r.stderr

def refresh():
    st.cache_data.clear()
    st.rerun()

# ── Imagens ───────────────────────────────────────────────────────────────────

from skills.image_fetcher import image_path_for, fetch_and_save, save_upload, fetch_all
from skills.video_fetcher import (
    video_path_for,
    save_upload as save_video_upload,
    delete as delete_video,
)
from skills.video_gen import gerar_video

def get_image(meme_id):
    return image_path_for(meme_id)

def get_video(meme_id):
    return video_path_for(meme_id)

def show_image(meme_id, width=300):
    p = get_image(meme_id)
    if p:
        st.image(str(p), width=width)
    return p

def zip_images(meme_ids):
    """Monta um ZIP em memória com as imagens dos ids informados."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for mid in meme_ids:
            p = get_image(mid)
            if p:
                zf.write(str(p), arcname=Path(p).name)
    buf.seek(0)
    return buf

# ── Constantes visuais ────────────────────────────────────────────────────────

STATUS_EMOJI = {"falso": "❌", "enganoso": "⚠️", "contexto_ausente": "🔍", "verdadeiro": "✅"}
ESTADO_EMOJI = {
    "discovered": "🔎", "fact_checking": "🔬", "enriching": "📊",
    "generating": "✍️", "reviewing": "🧐", "approved": "✅", "rejected": "❌",
}

# ── Sidebar ───────────────────────────────────────────────────────────────────

with st.sidebar:
    st.title("🎮 OzielMemes")
    st.caption("Cidadania Conectada: Vozes do Oziel")
    st.divider()

    pagina = st.radio(
        "nav", ["📊 Dashboard", "📋 Memes", "🔄 Fila", "⚙️ Pipeline", "🖼️ Galeria"],
        label_visibility="collapsed",
    )
    st.divider()

    st.markdown("**Ações rápidas**")
    if st.button("▶️ Rodar pipeline", use_container_width=True, type="primary"):
        with st.spinner("Rodando…"):
            out = run_cmd(["--max", "10"])
        st.cache_data.clear()
        st.success("Concluído!")
        st.text(out[-1000:])

    if st.button("🔁 Retry falhas", use_container_width=True):
        out = run_cmd(["--retry-failed"])
        st.cache_data.clear()
        st.text(out)

    if st.button("🃏 Gerar cards", use_container_width=True):
        with st.spinner("Exportando…"):
            out = run_cmd(["--gerar-cards"])
        st.text(out[-1000:])

    if st.button("📷 Buscar todas as imagens", use_container_width=True):
        memes = load_memes()
        com_url = [m for m in memes if m.get("source_url")]
        if com_url:
            with st.spinner(f"Buscando imagens de {len(com_url)} memes…"):
                results = fetch_all(com_url)
            st.cache_data.clear()
            st.success(f"{len(results)} imagens baixadas")
        else:
            st.info("Nenhum meme com URL de origem.")

    if st.button("🔃 Atualizar", use_container_width=True):
        refresh()

# ═════════════════════════════════════════════════════════════════════════════
# DASHBOARD
# ═════════════════════════════════════════════════════════════════════════════
if pagina == "📊 Dashboard":
    st.title("📊 Dashboard")

    stats, fila = load_stats()
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Memes no banco", stats.get("total") or 0)
    c2.metric("Aprovados", fila.get("approved", 0))
    c3.metric("No jogo", stats.get("no_jogo") or 0)
    c4.metric("Com TikTok", stats.get("com_tiktok") or 0)

    st.divider()
    col_fila, col_cat = st.columns(2)

    with col_fila:
        st.subheader("Estado da fila")
        fila_data = [
            {"Estado": f"{ESTADO_EMOJI.get(k,'•')} {k}", "Itens": v}
            for k, v in sorted(fila.items(), key=lambda x: -x[1])
        ]
        st.dataframe(fila_data, use_container_width=True, hide_index=True)

    with col_cat:
        st.subheader("Por categoria")
        memes = load_memes()
        cats: dict[str, int] = {}
        for m in memes:
            c = m.get("categoria") or "—"
            cats[c] = cats.get(c, 0) + 1
        st.dataframe(
            [{"Categoria": k, "Qtd": v} for k, v in sorted(cats.items(), key=lambda x: -x[1])],
            use_container_width=True, hide_index=True,
        )

    st.divider()
    st.subheader("Últimos memes")
    ultimos = sorted(memes, key=lambda m: m.get("created_at") or "", reverse=True)[:6]
    cols = st.columns(3)
    for i, m in enumerate(ultimos):
        with cols[i % 3]:
            verif = load_verificacao(m["id"])
            status = verif.get("status", "?") if verif else "?"
            emoji = STATUS_EMOJI.get(status, "•")
            st.markdown(f"**{emoji} {m.get('categoria','').upper()}**")
            img = get_image(m["id"])
            if img:
                st.image(str(img), use_container_width=True)
            else:
                st.caption("_(sem imagem)_")
            st.caption(f"`{m['id']}` · {m.get('meme_texto','')[:60]}…")

# ═════════════════════════════════════════════════════════════════════════════
# MEMES
# ═════════════════════════════════════════════════════════════════════════════
elif pagina == "📋 Memes":
    st.title("📋 Memes")
    memes = load_memes()

    # Filtros sem digitação
    cf1, cf2, cf3 = st.columns(3)
    cats = ["Todas"] + sorted({m.get("categoria") or "—" for m in memes})
    cat_filtro = cf1.selectbox("Categoria", cats)
    mods = ["Todos"] + sorted({m.get("modulo") or "—" for m in memes})
    mod_filtro = cf2.selectbox("Módulo", mods)
    status_ops = ["Todos", "falso", "enganoso", "contexto_ausente", "verdadeiro"]
    status_filtro = cf3.selectbox("Fact-check", status_ops)

    filtrados = memes
    if cat_filtro != "Todas":
        filtrados = [m for m in filtrados if m.get("categoria") == cat_filtro]
    if mod_filtro != "Todos":
        filtrados = [m for m in filtrados if m.get("modulo") == mod_filtro]
    if status_filtro != "Todos":
        filtrados = [
            m for m in filtrados
            if (load_verificacao(m["id"]) or {}).get("status") == status_filtro
        ]

    st.caption(f"{len(filtrados)} de {len(memes)} memes")
    st.divider()

    for m in filtrados:
        verif = load_verificacao(m["id"])
        status = verif.get("status", "?") if verif else "?"
        emoji = STATUS_EMOJI.get(status, "•")
        conteudo = load_conteudo(m["id"])
        tem_img = "🖼️ " if get_image(m["id"]) else ""
        tem_video = "🎬 " if get_video(m["id"]) else ""

        with st.expander(f"{tem_video}{tem_img}{emoji}  {m.get('meme_texto','')[:75]}"):
            col_img, col_info = st.columns([1, 2])

            # ── Coluna imagem ─────────────────────────────────────────────
            with col_img:
                img = get_image(m["id"])
                if img:
                    st.image(str(img), use_container_width=True)
                else:
                    st.caption("Sem imagem")

                # Botão buscar (só se tem URL)
                if m.get("source_url"):
                    if st.button("📷 Buscar imagem", key=f"fetch_{m['id']}"):
                        with st.spinner("Baixando…"):
                            p = fetch_and_save(m["id"], m["source_url"])
                        if p:
                            st.success("Imagem salva!")
                            st.cache_data.clear()
                            st.rerun()
                        else:
                            st.warning("Imagem não encontrada no artigo.")

                # Upload manual
                upload = st.file_uploader(
                    "📁 Upload manual", type=["jpg","jpeg","png","webp"],
                    key=f"up_{m['id']}", label_visibility="collapsed"
                )
                if upload:
                    save_upload(m["id"], upload.read(), upload.name)
                    st.success("Imagem salva!")
                    st.cache_data.clear()
                    st.rerun()

                # ── Vídeo da pílula/campanha ──────────────────────────
                st.divider()
                vid = get_video(m["id"])
                if vid:
                    st.video(str(vid))
                    if st.button("🗑️ Remover vídeo", key=f"delvid_{m['id']}"):
                        delete_video(m["id"])
                        st.cache_data.clear()
                        st.rerun()
                else:
                    st.caption("🎬 Sem vídeo")
                vid_upload = st.file_uploader(
                    "🎬 Upload vídeo da pílula", type=["mp4", "webm", "mov", "m4v"],
                    key=f"vidup_{m['id']}", label_visibility="collapsed"
                )
                if vid_upload:
                    save_video_upload(m["id"], vid_upload.read(), vid_upload.name)
                    st.success("Vídeo salvo!")
                    st.cache_data.clear()
                    st.rerun()

                # ── Gerar pílula em vídeo com IA (TTS + imagem do meme) ──
                opcoes_pilula = {
                    "Pílula de sabedoria": (conteudo or {}).get("pilula_sabedoria"),
                    "Alt 1 (emocional)": (conteudo or {}).get("pilula_alt1"),
                    "Alt 2 (chamada pra ação)": (conteudo or {}).get("pilula_alt2"),
                }
                opcoes_pilula = {k: v for k, v in opcoes_pilula.items() if v}
                if opcoes_pilula:
                    escolha = st.selectbox(
                        "Texto pra narrar", list(opcoes_pilula),
                        key=f"vidtxt_{m['id']}", label_visibility="collapsed",
                    )
                    tem_pexels = bool(os.environ.get("PEXELS_API_KEY"))
                    estilos = {"🖼️ Imagem do meme": "imagem"}
                    if tem_pexels:
                        estilos["🎞️ B-roll (Pexels + legendas)"] = "broll"
                    estilo_label = st.radio(
                        "Estilo", list(estilos), key=f"vidstyle_{m['id']}", horizontal=True,
                    )
                    if st.button("🎬 Gerar pílula em vídeo (IA)", key=f"vidgen_{m['id']}"):
                        with st.spinner("Narrando e montando o vídeo…"):
                            try:
                                gerar_video(
                                    m["id"], opcoes_pilula[escolha],
                                    estilo=estilos[estilo_label],
                                )
                                st.success("Vídeo gerado!")
                                st.cache_data.clear()
                                st.rerun()
                            except Exception as e:
                                st.error(f"Falhou: {e}")

            # ── Coluna informações ────────────────────────────────────────
            with col_info:
                tabs = st.tabs(["📄 Meme", "🔍 Dado oculto", "🔬 Fact-check", "📊 Dados abertos"])

                with tabs[0]:
                    c1, c2 = st.columns(2)
                    c1.write(f"**ID:** `{m['id']}`")
                    c1.write(f"**Categoria:** {m.get('categoria','—')}")
                    c1.write(f"**Módulo:** {m.get('modulo','—')}")
                    c1.write(f"**Dificuldade:** {'⭐' * (m.get('dificuldade') or 2)}")
                    tags = m.get("tags") or []
                    if isinstance(tags, str):
                        try: tags = json.loads(tags)
                        except: tags = [tags]
                    c2.write(f"**Tags:** {', '.join(tags) if tags else '—'}")
                    c2.write(f"**No jogo:** {'✅' if m.get('usado_no_jogo') else '—'}")
                    c2.write(f"**TikTok:** {'✅' if m.get('roteiro_tiktok') else '—'}")
                    if m.get("source_url"):
                        st.markdown(f"[🔗 Artigo original]({m['source_url']})")
                    st.text_area(
                        "Texto do meme", m.get("meme_texto",""),
                        height=80, disabled=True, key=f"txt_{m['id']}"
                    )

                    # ── Preview card do jogo ──────────────────────────────
                    st.caption("Preview — como aparece no jogo")
                    _verif = load_verificacao(m["id"])
                    _status = _verif.get("status", "") if _verif else ""
                    _badge = STATUS_EMOJI.get(_status, "")
                    _modulo = (m.get("modulo") or "").upper()
                    _texto = m.get("meme_texto", "").replace("<", "&lt;").replace(">", "&gt;")
                    _img_path = get_image(m["id"])
                    _img_html = ""
                    if _img_path:
                        import base64
                        _img_bytes = Path(_img_path).read_bytes()
                        _img_b64 = base64.b64encode(_img_bytes).decode()
                        _ext = Path(_img_path).suffix.lstrip(".").lower()
                        _mime = "image/jpeg" if _ext in ("jpg", "jpeg") else f"image/{_ext}"
                        _img_html = (
                            f'<img src="data:{_mime};base64,{_img_b64}" '
                            f'style="width:100%;max-height:120px;object-fit:cover;'
                            f'border-radius:8px 8px 0 0;display:block;" />'
                        )
                    _badge_html = (
                        f'<span style="position:absolute;top:10px;right:12px;'
                        f'font-size:18px;">{_badge}</span>'
                        if _badge else ""
                    )
                    _card_html = f"""
<div style="
    background:#1C1C1E;
    border:1px solid #2C2C2E;
    border-radius:16px;
    max-width:320px;
    margin:8px auto;
    overflow:hidden;
    position:relative;
    font-family:system-ui,sans-serif;
">
    {_img_html}
    {_badge_html}
    <div style="padding:14px 16px 6px 16px;">
        <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:12px;">
            <span style="font-family:monospace;font-size:11px;color:#888;text-transform:uppercase;letter-spacing:1px;">{_modulo}</span>
            <span style="font-family:monospace;font-size:11px;color:#555;">arrastar →</span>
        </div>
        <p style="color:#F5F0E8;font-size:20px;font-weight:700;text-align:center;margin:16px 0 20px 0;line-height:1.35;">{_texto}</p>
    </div>
    <div style="padding:10px 16px 14px 16px;border-top:1px solid #2C2C2E;">
        <span style="font-family:monospace;font-size:11px;color:#555;">← discordo &nbsp;&nbsp;/&nbsp;&nbsp; concordo →</span>
    </div>
</div>
"""
                    st.markdown(_card_html, unsafe_allow_html=True)

                with tabs[1]:
                    # Aba Freakonomics — dado oculto
                    if conteudo:
                        if conteudo.get("objetivo_meme"):
                            st.markdown("#### 🎭 Objetivo do meme")
                            st.warning(conteudo["objetivo_meme"])
                        st.markdown("#### 🎯 O que este meme esconde")
                        st.info(conteudo.get("contexto_oculto","—"))
                        st.markdown("#### 💡 Pílula de sabedoria")
                        st.success(conteudo.get("pilula_sabedoria","—"))
                        # Alternativas pro vídeo da campanha
                        _alt1 = conteudo.get("pilula_alt1")
                        _alt2 = conteudo.get("pilula_alt2")
                        if _alt1 or _alt2:
                            st.markdown("#### 🎬 Alternativas pro vídeo da campanha")
                            if _alt1:
                                st.caption("Ângulo emocional/pessoal")
                                st.success(_alt1)
                            if _alt2:
                                st.caption("Ângulo factual/chamada-pra-ação")
                                st.success(_alt2)
                        if conteudo.get("roteiro_tiktok"):
                            st.markdown("#### 📱 Roteiro TikTok — Cena 3 (a revelação)")
                            st.text_area(
                                "", conteudo["roteiro_tiktok"],
                                height=100, disabled=True, key=f"tiktok_{m['id']}"
                            )
                        st.caption(f"Modelo: `{conteudo.get('modelo_claude','—')}` · v`{conteudo.get('prompt_version','—')}`")
                    else:
                        st.info("Conteúdo ainda não gerado para este meme.")
                        if st.button("▶️ Gerar agora", key=f"gen_{m['id']}"):
                            st.info("Rode o pipeline completo pelo sidebar para gerar.")

                with tabs[2]:
                    if verif:
                        s1, s2 = st.columns(2)
                        s1.metric("Status", f"{STATUS_EMOJI.get(verif.get('status',''),'?')} {verif.get('status','—')}")
                        s1.write(f"**Agência:** {verif.get('agencia','—')}")
                        s1.write(f"**Fonte:** {verif.get('fonte','—')}")
                        if verif.get("fonte_url"):
                            s2.markdown(f"[🔗 Verificação]({verif['fonte_url']})")
                        st.text_area(
                            "Explicação", verif.get("explicacao",""),
                            height=80, disabled=True, key=f"expl_{m['id']}"
                        )
                    else:
                        st.info("Sem verificação registrada.")

                with tabs[3]:
                    dps = load_data_points(m["id"])
                    if dps:
                        dp_rows = [
                            {
                                "Indicador": d.get("indicador",""),
                                "Valor": f"{d.get('valor','')} {d.get('unidade','')}".strip(),
                                "Localidade": d.get("localidade_nome",""),
                                "Ano": d.get("ano_referencia",""),
                                "Fonte": d.get("fonte",""),
                            }
                            for d in dps
                        ]
                        st.dataframe(dp_rows, use_container_width=True, hide_index=True)
                    else:
                        st.info("Sem dados abertos vinculados.")

# ═════════════════════════════════════════════════════════════════════════════
# FILA
# ═════════════════════════════════════════════════════════════════════════════
elif pagina == "🔄 Fila":
    st.title("🔄 Fila do Pipeline")

    _, fila = load_stats()
    estado_sel = st.selectbox(
        "Estado",
        list(ESTADO_EMOJI.keys()),
        format_func=lambda e: f"{ESTADO_EMOJI.get(e,'')} {e} ({fila.get(e,0)})",
    )

    itens = load_fila(estado_sel)
    st.caption(f"{len(itens)} item(s)")

    if itens:
        rows = [
            {
                "ID": it.get("id"),
                "Meme": (it.get("meme_texto_raw") or "")[:60],
                "Tentativas": it.get("tentativas",0),
                "Meme ID": it.get("meme_id") or "—",
                "Erro": (it.get("erro_ultimo") or "")[:70],
            }
            for it in itens
        ]
        st.dataframe(rows, use_container_width=True, hide_index=True)
    else:
        st.info(f"Nenhum item em '{estado_sel}'.")

# ═════════════════════════════════════════════════════════════════════════════
# PIPELINE
# ═════════════════════════════════════════════════════════════════════════════
elif pagina == "⚙️ Pipeline":
    st.title("⚙️ Pipeline")

    st.subheader("Executar")
    c1, c2, c3 = st.columns(3)

    if c1.button("▶️ Rodar (10 itens)", use_container_width=True, type="primary"):
        with st.spinner("Rodando pipeline…"):
            out = run_cmd(["--max", "10"])
        st.cache_data.clear()
        st.text(out)

    if c2.button("🔍 Dry-run (só pesquisa)", use_container_width=True):
        with st.spinner("Pesquisando…"):
            out = run_cmd(["--dry-run"])
        st.cache_data.clear()
        st.text(out)

    if c3.button("🔁 Retry de falhas", use_container_width=True):
        out = run_cmd(["--retry-failed"])
        st.cache_data.clear()
        st.text(out)

    st.divider()
    st.subheader("Exportar")
    e1, e2, e3, e4 = st.columns(4)

    if e1.button("🃏 Gerar cards (.ts + .json)", use_container_width=True):
        with st.spinner("Exportando…"):
            out = run_cmd(["--gerar-cards"])
        st.text(out)

    if e2.button("📱 Gerar roteiros TikTok", use_container_width=True):
        with st.spinner("Gerando roteiros…"):
            out = run_cmd(["--gerar-tiktok"])
        st.text(out)

    if e3.button("📥 Reimportar memes.json", use_container_width=True):
        with st.spinner("Importando…"):
            out = run_cmd(["--from-json"])
        st.cache_data.clear()
        st.text(out)

    if e4.button("🚀 Exportar pro jogo", use_container_width=True, type="primary"):
        with st.spinner("Gerando e copiando dilemas_gerados.ts…"):
            out = run_cmd(["--gerar-cards"])
        _src = ROOT / "output" / "dilemas" / "dilemas_gerados.ts"
        _dst = Path("/home/dan/Área de Trabalho/jogo_ozipa/src/lib/dilemas_gerados.ts")
        # O arquivo exportado é importado pelo jogo em dilemas_gerados.ts (stub vazio por padrão)
        if _src.exists():
            _content = _src.read_text(encoding="utf-8")
            _dst.parent.mkdir(parents=True, exist_ok=True)
            _dst.write_text(_content, encoding="utf-8")
            st.success("✅ dilemas_gerados.ts copiado pro jogo!")
            st.code(_content[:500] + "...", language="typescript")
        else:
            st.warning(f"Arquivo não encontrado: {_src}")
            st.text(out)

    st.divider()
    st.subheader("Imagens")
    i1, i2 = st.columns(2)

    if i1.button("📷 Buscar imagens (todas com URL)", use_container_width=True):
        memes = load_memes()
        com_url = [m for m in memes if m.get("source_url")]
        with st.spinner(f"Buscando em {len(com_url)} artigos…"):
            results = fetch_all(com_url)
        st.cache_data.clear()
        if results:
            st.success(f"{len(results)} imagens salvas")
        else:
            st.warning("Nenhuma imagem encontrada.")

    # Mostra quais têm/não têm imagem
    memes = load_memes()
    sem_img = [m for m in memes if not get_image(m["id"])]
    com_img = [m for m in memes if get_image(m["id"])]
    i2.metric("Com imagem", len(com_img))
    i2.metric("Sem imagem", len(sem_img))

    st.divider()
    st.subheader("Output gerado")
    output_dir = ROOT / "output" / "dilemas"
    if output_dir.exists():
        for f in sorted(output_dir.iterdir()):
            size = f.stat().st_size // 1024
            col_a, col_b = st.columns([3, 1])
            col_a.write(f"`{f.name}` — {size}KB")
            with open(f) as fh:
                col_b.download_button(
                    "⬇️ Download", fh.read(), file_name=f.name, key=f"dl_{f.name}"
                )
    else:
        st.info("Nenhum output gerado ainda. Clique em 'Gerar cards'.")

# ═════════════════════════════════════════════════════════════════════════════
# GALERIA
# ═════════════════════════════════════════════════════════════════════════════
elif pagina == "🖼️ Galeria":
    st.title("🖼️ Galeria de Memes")

    memes = load_memes()
    com_img = [m for m in memes if get_image(m["id"])]
    sem_img = [m for m in memes if not get_image(m["id"])]

    st.metric("Memes com imagem", f"{len(com_img)} de {len(memes)}")

    # Download de todas de uma vez
    if com_img:
        st.download_button(
            label=f"📦 Baixar todas ({len(com_img)}) (ZIP)",
            data=zip_images([m["id"] for m in com_img]),
            file_name="memes_todos.zip",
            mime="application/zip",
        )
    st.divider()

    # Grid de memes com imagem
    if com_img:
        cols = st.columns(3)
        for i, m in enumerate(com_img):
            with cols[i % 3]:
                img_path = get_image(m["id"])
                st.image(str(img_path), use_container_width=True)
                checked = st.checkbox(
                    m["id"], key=f"sel_{m['id']}",
                    label_visibility="visible"
                )
                # Download individual da imagem
                st.download_button(
                    "⬇️ Baixar",
                    data=Path(img_path).read_bytes(),
                    file_name=Path(img_path).name,
                    mime=f"image/{Path(img_path).suffix.lstrip('.').lower() or 'jpeg'}",
                    key=f"dl_img_{m['id']}",
                    use_container_width=True,
                )
                st.caption(f"{m.get('meme_texto','')[:60]}…")

        st.divider()

        # Botão de download ZIP das selecionadas
        selecionados = [m["id"] for m in com_img if st.session_state.get(f"sel_{m['id']}")]
        if selecionados:
            st.download_button(
                label=f"📥 Baixar selecionadas ({len(selecionados)}) (ZIP)",
                data=zip_images(selecionados),
                file_name="memes_selecionados.zip",
                mime="application/zip",
                type="primary",
            )
        else:
            st.button("📥 Baixar selecionadas (ZIP)", disabled=True, use_container_width=False)
    else:
        st.info("Nenhum meme com imagem ainda. Use o pipeline para buscar imagens.")

    # Seção memes sem imagem
    if sem_img:
        st.divider()
        st.subheader(f"Sem imagem ({len(sem_img)})")
        for m in sem_img:
            st.caption(f"`{m['id']}` — {m.get('meme_texto','')[:80]}")
