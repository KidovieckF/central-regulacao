// app/static/js/chat.js
document.addEventListener("DOMContentLoaded", () => {
  console.debug("chat.js: DOMContentLoaded");
  const socket = io(); // usa cookie de sessão flask-login
  const tabsEl = document.getElementById("chat-tabs");
  const messagesEl = document.getElementById("messages");
  const form = document.getElementById("chat-form");
  const input = document.getElementById("message-input");
  const fileInput = document.getElementById("file-input");
  const attachBtn = document.getElementById("attach-btn");
  const preview = document.getElementById("attachments-preview");

  let currentConv = null;
  let attachmentsMeta = [];

  // buscar abas (com tratamento de erro e placeholder quando vazio)
  fetch("/chat/tabs").then(r=>{
    if (!r.ok) throw new Error(`HTTP ${r.status}`);
    return r.json();
  }).then(tabs=>{
    console.debug("chat.js: /chat/tabs returned", tabs);
    if (!tabs || !tabs.length){
      tabsEl.innerHTML = "<div class=\"muted\">Nenhuma conversa disponível</div>";
      return;
    }
    tabs.forEach(t=>{
      const btn = document.createElement("button");
      btn.innerText = t.label;
      btn.onclick = ()=> openConv(t.conversation_id, t.target_role);
      tabsEl.appendChild(btn);
    });
  }).catch(err=>{
    console.error("Erro ao buscar abas:", err);
    tabsEl.innerHTML = "<div class=\"text-danger\">Não foi possível carregar conversas</div>";
  });

  socket.on("connected", d => console.log("connected", d));
  socket.on("message:new", msg => {
    console.debug("socket message:new received", msg);
    if (msg.conversation_id !== currentConv) return;
    renderMessage(msg);
  });

  // mostrar erros emitidos pelo servidor (por exemplo permission_denied)
  socket.on("error", e => {
    console.error("socket error", e);
    if (e && e.error) alert(`Erro socket: ${e.error}`);
  });

  function openConv(convId, targetRole){
    if (currentConv) socket.emit("leave_conversation",{conversation_id:currentConv});
    currentConv = convId;
    // manter target role global para envio posterior (o servidor valida permissões usando isto)
    window.current_target_role = targetRole || null;
    messagesEl.innerHTML = "";
    socket.emit("join_conversation", {conversation_id:convId, target_role: targetRole});
    console.debug("openConv: fetching history for conv", convId, "target_role", targetRole);
    fetch(`/chat/history/${convId}`)
      .then(async r => {
        if (!r.ok) {
          const text = await r.text();
          console.error("history fetch failed:", r.status, text);
          // tentar parse JSON de erro
          try {
            const err = JSON.parse(text);
            alert(`Erro ao carregar histórico: ${err.error || err.message || r.status}`);
          } catch (ex) {
            alert(`Erro ao carregar histórico (status ${r.status}). Veja o console para mais detalhes.`);
          }
          return [];
        }
        return r.json();
      })
      .then(list=>{
        console.debug("history list", list);
        if (!list || !list.length) return;
        list.forEach(renderMessage);
      })
      .catch(err=>{
        console.error("Erro ao buscar histórico:", err);
        alert("Não foi possível obter histórico de mensagens. Veja console para detalhes.");
      });
  }

  function renderMessage(msg){
    const el = document.createElement("div");
    el.innerHTML = `<b>${msg.sender_name}</b>: ${msg.text || ""}<div class="time">${msg.created_at || ""}</div>`;
    if (msg.attachments && msg.attachments.length){
      const ul = document.createElement("ul");
      msg.attachments.forEach(a=>{
        const li = document.createElement("li");
        const a_el = document.createElement("a");
        a_el.href = `/static/uploads/${a.stored_filename}`;
        a_el.target = "_blank";
        a_el.innerText = a.original_filename;
        li.appendChild(a_el);
        ul.appendChild(li);
      });
      el.appendChild(ul);
    }
    messagesEl.appendChild(el);
    messagesEl.scrollTop = messagesEl.scrollHeight;
  }

  attachBtn.addEventListener("click", ()=>fileInput.click());
  fileInput.addEventListener("change", async (ev)=>{
    const files = ev.target.files;
    if (!files.length) return;
    const fd = new FormData();
    for (let f of files) fd.append("files", f);
  const res = await fetch("/chat/upload", {method:"POST", body:fd});
  console.debug("upload response status", res.status);
  const body = await res.json();
    if (body.files){
      attachmentsMeta = body.files;
      preview.innerHTML = body.files.map(f=>`<div>${f.original_filename}</div>`).join("");
    } else {
      alert("Erro upload");
    }
  });

  form.addEventListener("submit", (e)=>{
    e.preventDefault();
    if (!currentConv) { alert("Selecione uma conversa"); return; }
    const payload = {
      conversation_id: currentConv,
      text: input.value,
      attachments: attachmentsMeta,
      target_role: window.current_target_role || null
    };
    console.debug("sending message payload", payload);
    socket.emit("send_message", payload);
    input.value = "";
    preview.innerHTML = "";
    attachmentsMeta = [];
  });
});
