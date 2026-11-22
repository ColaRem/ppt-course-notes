(function () {
  "use strict";

  var toastTimer = null;
  function toast(message) {
    var el = document.getElementById("toast");
    if (!el) return;
    el.textContent = message;
    el.hidden = false;
    if (toastTimer) clearTimeout(toastTimer);
    toastTimer = setTimeout(function () {
      el.hidden = true;
    }, 1800);
  }

  /* Tabs ---------------------------------------------------------------- */
  var tabs = Array.prototype.slice.call(document.querySelectorAll(".detail-tab"));
  tabs.forEach(function (tab) {
    tab.addEventListener("click", function () {
      tabs.forEach(function (item) {
        var active = item === tab;
        item.classList.toggle("active", active);
        item.setAttribute("aria-selected", active ? "true" : "false");
      });
      var study = document.getElementById("panel-study");
      var mindmap = document.getElementById("panel-mindmap");
      if (study) study.hidden = tab.dataset.tab !== "study";
      if (mindmap) mindmap.hidden = tab.dataset.tab !== "mindmap";
    });
  });

  /* Chapter accordion --------------------------------------------------- */
  Array.prototype.forEach.call(
    document.querySelectorAll("[data-chapter-toggle]"),
    function (button) {
      button.addEventListener("click", function () {
        var body = button.nextElementSibling;
        if (!body) return;
        var open = button.getAttribute("aria-expanded") === "true";
        button.setAttribute("aria-expanded", open ? "false" : "true");
        body.hidden = open;
        var arrow = button.querySelector(".chapter-arrow");
        if (arrow) arrow.textContent = open ? "+" : "−";
      });
    }
  );

  /* Exercise answers ---------------------------------------------------- */
  Array.prototype.forEach.call(
    document.querySelectorAll(".example-toggle"),
    function (button) {
      button.addEventListener("click", function () {
        var card = button.closest(".example-card");
        if (!card) return;
        var answer = card.querySelector(".example-answer");
        if (!answer) return;
        var open = button.getAttribute("aria-expanded") === "true";
        button.setAttribute("aria-expanded", open ? "false" : "true");
        button.textContent = open ? "查看答案" : "收起答案";
        answer.hidden = open;
      });
    }
  );

  /* Markdown actions ---------------------------------------------------- */
  var markdown = "";
  try {
    var data = document.getElementById("markdown-data");
    markdown = data ? JSON.parse(data.textContent) : "";
  } catch (error) {
    markdown = "";
  }

  function copyText(text) {
    if (navigator.clipboard && navigator.clipboard.writeText) {
      return navigator.clipboard.writeText(text).then(
        function () {
          return true;
        },
        function () {
          return fallbackCopy(text);
        }
      );
    }
    return Promise.resolve(fallbackCopy(text));
  }

  function fallbackCopy(text) {
    var area = document.createElement("textarea");
    area.value = text;
    area.setAttribute("readonly", "");
    area.style.position = "fixed";
    area.style.opacity = "0";
    document.body.appendChild(area);
    area.select();
    var ok = false;
    try {
      ok = document.execCommand("copy");
    } catch (error) {
      ok = false;
    }
    document.body.removeChild(area);
    return ok;
  }

  var copyButton = document.getElementById("copy-md");
  if (copyButton) {
    copyButton.addEventListener("click", function () {
      copyText(markdown).then(function (ok) {
        toast(ok ? "Markdown 已复制" : "复制失败，请手动选择文本");
      });
    });
  }

  var downloadButton = document.getElementById("download-md");
  if (downloadButton) {
    downloadButton.addEventListener("click", function () {
      if (!markdown) return;
      var name = document.title.split(" · ")[0].replace(/[\\/:*?"<>|]+/g, "_");
      var blob = new Blob([markdown], { type: "text/markdown;charset=utf-8" });
      var url = URL.createObjectURL(blob);
      var link = document.createElement("a");
      link.href = url;
      link.download = (name || "学习资料") + ".md";
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
      setTimeout(function () {
        URL.revokeObjectURL(url);
      }, 1000);
      toast("已保存 Markdown 文档");
    });
  }

  /* Mind map ------------------------------------------------------------ */
  var scale = 1;
  var scaleBox = document.querySelector(".mm-scale");
  var scaleLabel = document.querySelector(".mm-scale-label");

  function setScale(value) {
    if (!scaleBox) return;
    scale = Math.min(1.6, Math.max(0.6, Math.round(value * 10) / 10));
    scaleBox.style.transform = "scale(" + scale + ")";
    if (scaleLabel) scaleLabel.textContent = Math.round(scale * 100) + "%";
  }

  Array.prototype.forEach.call(
    document.querySelectorAll("[data-mm-zoom]"),
    function (button) {
      button.addEventListener("click", function () {
        setScale(scale + Number(button.dataset.mmZoom || 0));
      });
    }
  );

  var resetButton = document.querySelector("[data-mm-reset]");
  if (resetButton) {
    resetButton.addEventListener("click", function () {
      setScale(1);
    });
  }

  Array.prototype.forEach.call(
    document.querySelectorAll("[data-mm-toggle]"),
    function (button) {
      button.addEventListener("click", function (event) {
        event.stopPropagation();
        var branch = button.closest(".mm-branch");
        if (!branch) return;
        var collapsed = branch.classList.toggle("mm-collapsed");
        button.textContent = collapsed ? "+" : "−";
        button.setAttribute("aria-label", collapsed ? "展开分支" : "折叠分支");
      });
    }
  );

  var mindmap = document.querySelector(".mm");
  var fullscreenButton = document.querySelector("[data-mm-fullscreen]");
  if (mindmap && fullscreenButton) {
    fullscreenButton.addEventListener("click", function () {
      var on = mindmap.classList.toggle("mm-fullscreen");
      fullscreenButton.textContent = on ? "✕" : "⛶";
      fullscreenButton.setAttribute("aria-label", on ? "退出全屏" : "全屏");
    });
  }

  var detail = document.querySelector(".mm-detail");
  var detailTitle = document.querySelector(".mm-detail-title");
  var detailNote = document.querySelector(".mm-detail-note");
  Array.prototype.forEach.call(
    document.querySelectorAll(".mm-node"),
    function (node) {
      node.addEventListener("click", function () {
        Array.prototype.forEach.call(
          document.querySelectorAll(".mm-node.selected"),
          function (item) {
            item.classList.remove("selected");
          }
        );
        node.classList.add("selected");
        if (!detail) return;
        detail.hidden = false;
        if (detailTitle) detailTitle.textContent = node.textContent;
        if (detailNote) {
          detailNote.textContent =
            node.dataset.note ||
            "该节点没有备注；可在导图中继续查看其他分支。";
        }
      });
    }
  );

  var closeButton = document.querySelector(".mm-detail-close");
  if (closeButton) {
    closeButton.addEventListener("click", function () {
      if (detail) detail.hidden = true;
    });
  }
})();