// === Live Preview for Add Card ===
function updateCardPreview() {
  const baseName = document.getElementById("base_name");
  const desc = document.getElementById("description");
  const imgBase = document.getElementById("image_base");
  const imgAwakened = document.getElementById("image_awakened");
  const imgEvent = document.getElementById("image_event");

  const name = baseName?.value || "Card";
  const description = desc?.value || "Description...";

  if (document.getElementById("title_base")) {
    document.getElementById("title_base").innerText = `${name} (Base)`;
    document.getElementById("desc_base").innerText = description;
    document.getElementById("img_base").src = imgBase?.value || "";
  }

  if (document.getElementById("title_awakened")) {
    document.getElementById("title_awakened").innerText = `${name} (Awakened)`;
    document.getElementById("desc_awakened").innerText = description;
    document.getElementById("img_awakened").src = imgAwakened?.value || "";
  }

  if (document.getElementById("title_event")) {
    document.getElementById("title_event").innerText = `${name} (Event)`;
    document.getElementById("desc_event").innerText = description;
    document.getElementById("img_event").src = imgEvent?.value || "";
  }
}

function initLivePreview() {
  const inputs = [
    "base_name",
    "description",
    "image_base",
    "image_awakened",
    "image_event"
  ];
  inputs.forEach(id => {
    const el = document.getElementById(id);
    if (el) el.addEventListener("input", updateCardPreview);
  });
  updateCardPreview();
}

// === Chart.js Donut for Dashboard ===
function renderFormChart(data) {
  const ctx = document.getElementById('formChart');
  if (!ctx) return;

  new Chart(ctx, {
    type: 'doughnut',
    data: {
      labels: ['Base', 'Awakened', 'Event'],
      datasets: [{
        data: data,
        backgroundColor: ['#3498db', 'gold', '#e91e63']
      }]
    },
    options: {
      plugins: {
        legend: {
          labels: { color: '#fff' }
        }
      }
    }
  });
}

// === Bootstrap Enhancements ===
function initBootstrap() {
  const tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
  tooltipTriggerList.forEach(el => new bootstrap.Tooltip(el));
}

// === Init on Load ===
window.addEventListener("DOMContentLoaded", () => {
  initLivePreview();
  initBootstrap();
});
