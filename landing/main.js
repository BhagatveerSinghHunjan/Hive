(() => {
  const macMeta = document.querySelector('meta[name="hive-download-mac"]');
  const winMeta = document.querySelector('meta[name="hive-download-win"]');
  const macUrl =
    (macMeta?.getAttribute("content") || "").trim() || "./downloads/HIVE-mac-arm64.zip";
  const winUrl =
    (winMeta?.getAttribute("content") || "").trim() || "./downloads/HIVE-windows-x64.zip";

  const params = new URLSearchParams(window.location.search);
  const override = (params.get("download") || "").trim();

  const wire = (el, url) => {
    if (!el) return;
    const finalUrl = override || url;
    el.setAttribute("href", finalUrl);
    if (/^https?:\/\//i.test(finalUrl)) {
      el.removeAttribute("download");
      el.setAttribute("target", "_blank");
      el.setAttribute("rel", "noopener noreferrer");
    } else {
      el.setAttribute("download", "");
    }
  };

  wire(document.getElementById("download-mac"), macUrl);
  wire(document.getElementById("download-mac-2"), macUrl);
  wire(document.getElementById("download-win"), winUrl);
  wire(document.getElementById("download-win-2"), winUrl);

  const note = document.getElementById("download-note");
  const ua = navigator.userAgent || "";
  const isWin = /Windows/i.test(ua);
  const isMac = /Mac OS X|Macintosh/i.test(ua);
  if (note) {
    if (isWin) note.textContent = "Detected Windows · use Download for Windows";
    else if (isMac) note.textContent = "Detected Mac · Apple Silicon build";
    else note.textContent = "macOS Apple Silicon · Windows 10/11 x64";
  }

  // Emphasize the matching platform button
  const preferWin = isWin && !isMac;
  const primary = preferWin
    ? [document.getElementById("download-win"), document.getElementById("download-win-2")]
    : [document.getElementById("download-mac"), document.getElementById("download-mac-2")];
  const secondary = preferWin
    ? [document.getElementById("download-mac"), document.getElementById("download-mac-2")]
    : [document.getElementById("download-win"), document.getElementById("download-win-2")];

  for (const el of primary.filter(Boolean)) {
    el.classList.remove("cta-secondary");
    el.classList.add("cta");
  }
  for (const el of secondary.filter(Boolean)) {
    el.classList.add("cta-secondary");
  }
})();
