(() => {
  const macMeta = document.querySelector('meta[name="hive-download-mac"]');
  const macUrl =
    (macMeta?.getAttribute("content") || "").trim() ||
    "https://github.com/BhagatveerSinghHunjan/Hive/releases/download/v0.1.0/HIVE-mac-arm64.zip";

  const wire = (el, url) => {
    if (!el) return;
    el.setAttribute("href", url);
    el.removeAttribute("download");
    el.setAttribute("target", "_blank");
    el.setAttribute("rel", "noopener noreferrer");
  };

  wire(document.getElementById("download-mac"), macUrl);
  wire(document.getElementById("download-mac-2"), macUrl);
})();
