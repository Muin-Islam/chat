const socket = io();

// ---------- text message ----------
document.getElementById("sendBtn").onclick = () => {
  const input = document.getElementById("msgInput");
  const text = input.value.trim();
  if (text) {
    socket.emit("text_message", text);
    input.value = "";
  }
};

// ---------- incoming messages ----------
socket.on("new_message", data => {
  appendMessage(data);
});

socket.on("user_status", data => {
  appendSystemMsg(data.msg);
});

// ---------- image upload ----------
document.getElementById("fileInput").addEventListener("change", async e => {
  const file = e.target.files[0];
  if (!file) return;
  const form = new FormData();
  form.append("file", file);

  const res = await fetch("/upload", { method: "POST", body: form });
  if (!res.ok) {
    alert("Upload failed");
  }
  e.target.value = ""; // reset
});

// ---------- helpers ----------
function appendMessage(data) {
  const wrap = document.getElementById("messages");
  const div = document.createElement("div");

  if (data.type === "text") {
    div.innerHTML = `<strong>${data.username}:</strong> ${data.content}`;
  } else if (data.type === "image") {
    div.innerHTML = `<strong>${data.username}:</strong><br>
                     <img src="${data.url}" class="chat-img">`;
  }
  wrap.appendChild(div);
  wrap.scrollTop = wrap.scrollHeight;
}

function appendSystemMsg(msg) {
  const wrap = document.getElementById("messages");
  const div = document.createElement("div");
  div.className = "sys";
  div.textContent = msg;
  wrap.appendChild(div);
  wrap.scrollTop = wrap.scrollHeight;
}
