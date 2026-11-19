document.addEventListener("DOMContentLoaded", () => {
  const toggle = document.getElementById("menuToggle");
  const sidebar = document.getElementById("sidebar");
  if (toggle && sidebar) toggle.addEventListener("click", () => sidebar.classList.toggle("open"));

  document.querySelectorAll(".flash").forEach((flash) => {
    setTimeout(() => { if (flash.isConnected) flash.classList.add("fade-out"); }, 5000);
    setTimeout(() => { if (flash.isConnected) flash.remove(); }, 5500);
  });

  const canvas = document.getElementById("paymentChart");
  if (canvas && window.Chart) {
    new Chart(canvas, {
      type: "line",
      data: {
        labels: ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"],
        datasets: [{
          label: "Payments received",
          data: window.paymentData || [],
          borderColor: "#2878d0",
          backgroundColor: "rgba(40,120,208,.10)",
          fill: true,
          tension: .38,
          pointRadius: 3,
          pointBackgroundColor: "#2878d0"
        }]
      },
      options: {
        responsive: true,
        plugins: { legend: { display: false } },
        scales: {
          y: { beginAtZero: true, grid: { color: "#edf1f6" }, ticks: { callback: value => "KES " + Number(value).toLocaleString() } },
          x: { grid: { display: false } }
        }
      }
    });
  }
});
