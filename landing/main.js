(() => {
  const meta = document.querySelector('meta[name="hive-download-url"]');
  const configured = (meta?.getAttribute("content") || "").trim();
  const params = new URLSearchParams(window.location.search);
  const fromQuery = (params.get("download") || "").trim();
  const url = fromQuery || configured || "./downloads/HIVE-mac.zip";

  const buttons = [
    document.getElementById("download-btn"),
    document.getElementById("download-btn-2"),
    document.getElementById("nav-download"),
  ].filter(Boolean);

  const note = document.getElementById("download-note");

  for (const btn of buttons) {
    if (btn.id === "nav-download" && url.startsWith("#")) continue;
    if (btn.tagName === "A" && btn.id !== "nav-download") {
      btn.setAttribute("href", url);
      if (/^https?:\/\//i.test(url)) {
        btn.removeAttribute("download");
        btn.setAttribute("target", "_blank");
        btn.setAttribute("rel", "noopener noreferrer");
      } else {
        btn.setAttribute("download", "");
      }
    }
  }

  if (note && /^https?:\/\/github\.com\//i.test(url)) {
    note.textContent = "macOS · downloads from GitHub Releases";
  }
})();
