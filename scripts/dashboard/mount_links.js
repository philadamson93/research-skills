// Make mount paths and relative links work wherever the page is opened (VM path, the Mac's own
// mount location, or a copy outside the mount). Inlined into every dashboard page by the builders.
(function () {
  const VM_ROOT = "/mnt/su-vista-uscentral1/";
  const HOME = "chaudhari_lab/phil/";          // planning/, plan-explainers/ ... live under this
  const DASH = HOME + "planning/dashboard/";
  function detectRoot() {
    const h = decodeURIComponent(location.href);
    const i = h.indexOf("/" + HOME);
    if (i >= 0) return h.slice(0, i + 1);       // e.g. file:///Volumes/su-vista-uscentral1/
    try { return localStorage.getItem("wd:mntRoot"); } catch (e) { return null; }
  }
  const root = detectRoot();
  const inPlace = decodeURIComponent(location.href).indexOf("/" + DASH) >= 0;
  window.mountUrl = function (p) {               // VM absolute path or mount-relative path -> URL here
    if (!root) return null;
    if (p.startsWith(VM_ROOT)) return root + p.slice(VM_ROOT.length);
    if (p.startsWith("planning/") || p.startsWith("plan-explainers/")) return root + HOME + p;
    return null;
  };
  function fix() {
    // 1. relative links (a.html, a.html#x) when this is a copy outside the dashboard folder
    if (!inPlace && root) document.querySelectorAll("a[href]").forEach(a => {
      const h = a.getAttribute("href");
      if (h && !/^[a-z]+:|^#|^\//i.test(h)) a.setAttribute("href", root + DASH + h);
    });
    // 2. absolute VM links
    document.querySelectorAll('a[href^="/mnt/"],a[href^="file:///mnt/"]').forEach(a => {
      const u = mountUrl(a.getAttribute("href").replace(/^file:\/\//, "")); if (u) a.href = u;
    });
    // 3. plain-text mount paths in code / .path elements become links
    document.querySelectorAll("code,.path").forEach(el => {
      if (el.closest("a") || el.dataset.ml) return;
      const t = el.textContent.trim(); const u = /^(\/mnt\/su-vista|planning\/|plan-explainers\/)/.test(t) && mountUrl(t.split(/\s/)[0]);
      if (u) { el.dataset.ml = 1; el.innerHTML = `<a href="${u}" style="color:inherit">${el.innerHTML}</a>`; }
    });
  }
  window.setMountRoot = function () {
    const v = prompt("Where is the su-vista-uscentral1 mount on this computer? (the folder that contains chaudhari_lab), e.g. /Volumes/su-vista-uscentral1", "");
    if (!v) return;
    try { localStorage.setItem("wd:mntRoot", "file://" + v.replace(/\/?$/, "/")); } catch (e) {}
    location.reload();
  };
  window.fixMountLinks = fix;
  document.addEventListener("DOMContentLoaded", () => {
    fix(); new MutationObserver(() => fix()).observe(document.body, { childList: true, subtree: true });
    if (!root && location.protocol === "file:") {   // served over the web there is no mount to link to
      const b = document.createElement("div");
      b.style.cssText = "position:fixed;bottom:10px;right:10px;z-index:99;background:#fff4e8;color:#b4540a;border:1px solid #b4540a;border-radius:8px;padding:6px 10px;font:12px sans-serif";
      b.innerHTML = 'Links to the mount need its location here. <a href="#" onclick="setMountRoot();return false">Set mount location</a>';
      document.body.appendChild(b);
    }
  });
})();
