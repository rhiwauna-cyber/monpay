let chartInstance = null;

document.addEventListener("DOMContentLoaded", () => {
  // === 1. AUTOMATIC SESSION & PAGE DETECTOR ===
  const loginForm = document.getElementById("loginForm");
  const isDashboardPage = document.getElementById("history-rows");

  // Jika berada di Halaman Dashboard, baru muat data user
  if (isDashboardPage) {
    loadUserData();
    initTransactionForms();
  }

  // === 2. HANDLER LOGIN FORM ===
  if (loginForm) {
    loginForm.addEventListener("submit", async (e) => {
      e.preventDefault();
      const usernameInput = document.getElementById("username").value;
      const passwordInput = document.getElementById("password").value;

      try {
        const res = await fetch("/api/login", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            username: usernameInput,
            password: passwordInput,
          }),
        });

        const data = await res.json();

        if (data.status === "success") {
          window.location.href = "/";
        } else {
          alert(data.message || "Login gagal!");
        }
      } catch (err) {
        console.error("Error login:", err);
        alert("Terjadi kesalahan koneksi server.");
      }
    });
  }
});

// === 3. FETCH USER DATA & RENDER ===
async function loadUserData() {
  try {
    const res = await fetch("/api/user-data");
    const data = await res.json();

    if (data.status === "success") {
      const welcomeEl = document.getElementById("welcome-text");
      const accEl = document.getElementById("acc-number");
      const balanceEl = document.getElementById("total-balance");

      if (welcomeEl)
        welcomeEl.innerText = `Selamat Datang, ${data.user.full_name}`;
      if (accEl) accEl.innerText = data.user.account_number;
      if (balanceEl)
        balanceEl.innerText = `Rp ${data.user.balance.toLocaleString("id-ID")}`;

      renderTransactions(data.transactions || []);
      renderAnalyticsChart(data.transactions || []);
    }
  } catch (err) {
    console.error("Gagal memuat data user:", err);
  }
}

// RENDER TABEL RIWAYAT
function renderTransactions(txs) {
  const tbody = document.getElementById("history-rows");
  if (!tbody) return;

  tbody.innerHTML = "";
  let totalOut = 0;
  let totalIn = 0;

  txs.forEach((tx) => {
    if (tx.type === "OUT") totalOut += tx.amount;
    if (tx.type === "IN") totalIn += tx.amount;

    const tr = document.createElement("tr");
    const isOut = tx.type === "OUT";

    // 1. Buat elemen kolom satu per satu secara aman (Anti XSS)
    const tdDate = document.createElement("td");
    tdDate.textContent = tx.date;

    const tdCategory = document.createElement("td");
    const spanBadge = document.createElement("span");
    spanBadge.className = "user-badge";
    spanBadge.textContent = tx.category;
    tdCategory.appendChild(spanBadge);

    const tdTitle = document.createElement("td");
    const strongTitle = document.createElement("strong");
    strongTitle.textContent = tx.title;
    tdTitle.appendChild(strongTitle);

    const tdRecipient = document.createElement("td");
    tdRecipient.textContent = tx.recipient;

    const tdAmount = document.createElement("td");
    tdAmount.className = isOut ? "text-danger" : "text-success";
    tdAmount.textContent = `${isOut ? "-" : "+"} Rp ${tx.amount.toLocaleString("id-ID")}`;

    // 2. Masukkan semua kolom ke dalam baris (tr)
    tr.appendChild(tdDate);
    tr.appendChild(tdCategory);
    tr.appendChild(tdTitle);
    tr.appendChild(tdRecipient);
    tr.appendChild(tdAmount);

    // 3. Masukkan baris ke tabel
    tbody.appendChild(tr);
  });

  const outEl = document.getElementById("total-out");
  const inEl = document.getElementById("total-in");

  if (outEl) outEl.innerText = `Rp ${totalOut.toLocaleString("id-ID")}`;
  if (inEl) inEl.innerText = `Rp ${totalIn.toLocaleString("id-ID")}`;
}

// RENDER MONITORING CHART
function renderAnalyticsChart(txs) {
  const chartEl = document.getElementById("analyticsChart");
  if (!chartEl) return;

  const ctx = chartEl.getContext("2d");
  if (chartInstance) chartInstance.destroy();

  const labels = txs
    .slice(0, 5)
    .map((t) => String(t.date).split(" ")[0])
    .reverse();
  const amounts = txs
    .slice(0, 5)
    .map((t) => t.amount)
    .reverse();

  chartInstance = new Chart(ctx, {
    type: "line",
    data: {
      labels: labels.length ? labels : ["Day 1", "Day 2", "Day 3"],
      datasets: [
        {
          label: "Volume Transaksi (Rp)",
          data: amounts.length ? amounts : [0, 0, 0],
          borderColor: "#00c6ff",
          backgroundColor: "rgba(0, 198, 255, 0.1)",
          fill: true,
          tension: 0.4,
        },
      ],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: { legend: { display: false } },
      scales: {
        x: { grid: { color: "#202e46" }, ticks: { color: "#8a99ad" } },
        y: { grid: { color: "#202e46" }, ticks: { color: "#8a99ad" } },
      },
    },
  });
}

// SWITCH TAB NAVIGATION
function switchTab(tabName) {
  document
    .querySelectorAll(".tab-page")
    .forEach((el) => el.classList.add("hidden"));
  document
    .querySelectorAll(".menu-item")
    .forEach((el) => el.classList.remove("active"));

  const targetTab = document.getElementById(`tab-${tabName}`);
  if (targetTab) targetTab.classList.remove("hidden");

  // Perbaikan kecil agar tombol aktif aman dari error event
  const clickedBtn = event ? event.currentTarget : null;
  if (clickedBtn) {
    clickedBtn.classList.add("active");
  }
}

// HANDLER LOGOUT
async function handleLogout() {
  await fetch("/api/logout", { method: "POST" });
  window.location.href = "/";
}

// HANDLER TRANSACTIONS
async function sendTransaction(payload) {
  try {
    const res = await fetch("/api/transaction", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    const data = await res.json();
    alert(data.message);
    if (data.status === "success") {
      loadUserData();
      switchTab("dashboard");
    }
  } catch (err) {
    alert("Gagal melakukan transaksi!");
  }
}

// INITIALIZE TRANSACTION FORMS SAFELY
function initTransactionForms() {
  const formTf = document.getElementById("form-transfer");
  if (formTf) {
    formTf.addEventListener("submit", (e) => {
      e.preventDefault();
      sendTransaction({
        type: "OUT",
        title: `Transfer ${document.getElementById("tf-type")?.value || ""}`,
        recipient: document.getElementById("tf-target")?.value || "",
        amount: parseFloat(document.getElementById("tf-amount")?.value || 0),
        category: "Transfer",
      });
    });
  }

  const formBills = document.getElementById("form-bills");
  if (formBills) {
    formBills.addEventListener("submit", (e) => {
      e.preventDefault();
      sendTransaction({
        type: "OUT",
        title: document.getElementById("bill-type")?.value || "",
        recipient: document.getElementById("bill-target")?.value || "",
        amount: parseFloat(document.getElementById("bill-amount")?.value || 0),
        category: "Utility",
      });
    });
  }

  const formEwallet = document.getElementById("form-ewallet");
  if (formEwallet) {
    formEwallet.addEventListener("submit", {
      // Perbaikan event listener form ewallet
    });
    formEwallet.addEventListener("submit", (e) => {
      e.preventDefault();
      const provider = document.getElementById("ewallet-provider")?.value || "";
      const target = document.getElementById("ewallet-target")?.value || "";
      sendTransaction({
        type: "OUT",
        title: `Top Up ${provider}`,
        recipient: `${provider} (${target})`,
        amount: parseFloat(
          document.getElementById("ewallet-amount")?.value || 0,
        ),
        category: "Top Up",
      });
    });
  }

  const formQris = document.getElementById("form-qris");
  if (formQris) {
    formQris.addEventListener("submit", (e) => {
      e.preventDefault();
      sendTransaction({
        type: "OUT",
        title: "Pembayaran QRIS",
        recipient: document.getElementById("qris-merchant")?.value || "",
        amount: parseFloat(document.getElementById("qris-amount")?.value || 0),
        category: "QRIS",
      });
    });
  }
}

// --- FITUR AUTO-LOCK / SESSION MANAGEMENT ---
let idleTimeoutDuration = 5 * 60 * 1000;
let idleTimer;

function triggerAutoLogout(reason) {
  console.log("Sesi berakhir karena: " + reason);
  fetch("/api/logout", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
  })
    .then(() => {
      window.location.href = "/";
    })
    .catch(() => {
      window.location.href = "/";
    });
}

function resetIdleTimer() {
  clearTimeout(idleTimer);
  idleTimer = setTimeout(() => {
    triggerAutoLogout("Tidak ada aktivitas (Idle timeout)");
  }, idleTimeoutDuration);
}

window.addEventListener("mousemove", resetIdleTimer);
window.addEventListener("keypress", resetIdleTimer);
window.addEventListener("click", resetIdleTimer);
window.addEventListener("scroll", resetIdleTimer);

document.addEventListener("visibilitychange", function () {
  if (document.hidden) {
    triggerAutoLogout("Aplikasi ditinggalkan atau laptop sleep");
  }
});

resetIdleTimer();
