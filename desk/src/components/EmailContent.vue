<template>
  <iframe
    ref="iframeRef"
    :srcdoc="htmlContent"
    class="prose-f block h-10 max-h-[500px] w-full"
  />
</template>

<script setup lang="ts">
import { dataTheme, getFontFamily, stripEmailColors } from "@/utils";
import { computed, ref, watch } from "vue";

const props = defineProps({
  content: {
    type: String,
    required: true,
  },
});

const iframeRef = ref<HTMLIFrameElement | null>(null);
const _content = ref(stripEmailColors(props.content));

// Get CSS path - in dev Vite serves it directly, in prod we need the built path
const cssHref = computed(() => {
  if (import.meta.env.DEV) {
    return "/src/index.css";
  }
  // In production, find the built CSS file from the document
  const links = document.querySelectorAll('link[rel="stylesheet"]');
  for (const link of links) {
    const href = link.getAttribute("href");
    if (href?.includes("/assets/helpdesk/desk/") && href.endsWith(".css")) {
      return href;
    }
  }
  // Fallback to a reasonable path
  return "/assets/helpdesk/desk/index.css";
});

const parser = new DOMParser();
const doc = parser.parseFromString(_content.value, "text/html");

const gmailReplyToContent = doc.querySelectorAll("div.gmail_quote");
const outlookReplyToContent = doc.querySelectorAll("div#appendonsend");
const replyToContent = doc.querySelectorAll("p.reply-to-content");

const citeQuoteContent = doc.querySelectorAll('blockquote[type="cite"]');
const outlookDesktopReplyContent = doc.querySelectorAll("div#divRplyFwdMsg");

if (doc.body.children.length === 0) {
  // Plain-text emails (e.g. from Thunderbird) arrive as text with newlines and no spacing losing formatting.
  const plainText = doc.body.innerHTML.replace(/\n\n/g, "\n");
  _content.value = foldPlainTextQuote(plainText);
} else if (gmailReplyToContent.length) {
  _content.value = parseReplyToContent(doc, "div.gmail_quote", true);
} else if (outlookReplyToContent.length) {
  _content.value = parseReplyToContent(doc, "div#appendonsend");
} else if (replyToContent.length) {
  _content.value = parseReplyToContent(doc, "p.reply-to-content");
} else if (citeQuoteContent.length) {
  // Apple Mail, Thunderbird and Roundcube (HTML mode) quote the earlier message in <blockquote type="cite">
  _content.value = parseReplyToContent(doc, 'blockquote[type="cite"]', true);
} else if (outlookDesktopReplyContent.length) {
  _content.value = parseReplyToContent(doc, "div#divRplyFwdMsg");
}

// Plain-text replies mark the earlier message with an attribution line ("On ... wrote:") and ">" prefixes.
// Fold everything from the first such line; the full text stays in the email and opens with the "..." button.
function foldPlainTextQuote(text: string) {
  const lines = text.split("\n");
  const attribution = /^\s*(On .{5,200} wrote:|Pada .{5,200} menulis:|-{2,}\s*(Original Message|Pesan Asli)\s*-{2,})\s*$/i;
  const quoted = /^\s*(&gt;|>)/;
  let cut = lines.findIndex((line) => attribution.test(line));
  if (cut === -1) cut = lines.findIndex((line) => quoted.test(line));
  const wrap = (body: string) => `<div class="whitespace-pre-wrap">${body}</div>`;
  // nothing before the quote (the reply is only a quotation): show it all
  if (cut === -1 || lines.slice(0, cut).join("").trim() === "") return wrap(text);
  const id = Math.random().toString(36).substring(2, 7);
  return (
    wrap(lines.slice(0, cut).join("\n")) +
    `<div class="replied-content"><label class="collapse" for="${id}">...</label>` +
    `<input id="${id}" class="replyCollapser" type="checkbox">` +
    `<div class="whitespace-pre-wrap">${lines.slice(cut).join("\n")}</div></div>`
  );
}

function parseReplyToContent(
  doc: Document,
  selector: string,
  forGmail = false
) {
  function handleAllInstances(doc: Document) {
    const replyToContentElements = doc.querySelectorAll(selector);
    if (replyToContentElements.length === 0) return;
    const replyToContentElement = replyToContentElements[0];
    replaceReplyToContent(replyToContentElement, forGmail);
    handleAllInstances(doc);
  }

  handleAllInstances(doc);
  return doc.body.innerHTML;
}

function replaceReplyToContent(
  replyToContentElement: Element,
  forGmail: boolean
) {
  if (!replyToContentElement) return;
  const randomId = Math.random().toString(36).substring(2, 7);
  const wrapper = doc.createElement("div");
  wrapper.classList.add("replied-content");

  const collapseLabel = doc.createElement("label");
  collapseLabel.classList.add("collapse");
  collapseLabel.setAttribute("for", randomId);
  collapseLabel.innerHTML = "...";
  wrapper.appendChild(collapseLabel);

  const collapseInput = doc.createElement("input");
  collapseInput.setAttribute("id", randomId);
  collapseInput.setAttribute("class", "replyCollapser");
  collapseInput.setAttribute("type", "checkbox");
  wrapper.appendChild(collapseInput);

  if (forGmail) {
    const prevSibling = replyToContentElement.previousElementSibling;
    if (prevSibling && prevSibling.tagName === "BR") {
      prevSibling.remove();
    }
    const cloned = replyToContentElement.cloneNode(true) as Element;
    cloned.classList.remove("gmail_quote");
    wrapper.appendChild(cloned);
  } else {
    const allSiblings = Array.from(
      replyToContentElement.parentElement?.children || []
    );
    const replyToContentIndex = allSiblings.indexOf(replyToContentElement);
    const followingSiblings = allSiblings.slice(replyToContentIndex + 1);

    if (followingSiblings.length === 0) return;

    const clonedFollowingSiblings = followingSiblings.map((sibling) =>
      sibling.cloneNode(true)
    );

    const div = doc.createElement("div");
    div.append(...clonedFollowingSiblings);
    wrapper.append(div);

    for (let i = replyToContentIndex + 1; i < allSiblings.length; i++) {
      replyToContentElement.parentElement?.removeChild(allSiblings[i]);
    }
  }

  replyToContentElement.parentElement?.replaceChild(
    wrapper,
    replyToContentElement
  );
}

const htmlContent = computed(
  () => `
  <!DOCTYPE html>
  <html>
  <head>
    <link rel="stylesheet" href="${cssHref.value}" />
    <base target="_blank" />
    <style>
      :root {
        --bg-surface-gray-3: #ededed;
        --bg-surface-gray-4: #e2e2e2;
      }
      [data-theme='dark'] {
        --bg-surface-gray-3: #343434;
        --bg-surface-gray-4: #424242;
      }
      .replied-content .collapse {
        margin: 10px 0 10px 0;
        visibility: visible;
        cursor: pointer;
        display: flex;
        font-size: larger;
        font-weight: 700;
        height: 12px;
        line-height: 0.1;
        color: #383838;
        background: #e8eaed;
        width: 23px;
        justify-content: center;
        border-radius: 5px;
      }
      .replied-content .collapse:hover {
        background: #dadce0;
      }
      [data-theme='dark'] .replied-content .collapse {
        color: #e2e2e2;
        background: #424242;
      }
      [data-theme='dark'] .replied-content .collapse:hover {
        background: #525252;
      }
      .replied-content .collapse + input {
        display: none;
      }
      .replied-content .collapse + input + div {
        display: none;
      }
      .replied-content .collapse + input:checked + div {
        display: block;
      }
      .email-content {
        word-break: break-word;
      }
      .email-content :is(:where(img):not(:where([class~='not-prose'], [class~='not-prose'] *))) {
        border-width: 0;
      }
      .email-content :where(img):not(:where([class~='not-prose'], [class~='not-prose'] *)) {
        margin: 0;
      }
      .email-content :where(blockquote p:first-of-type):not(:where([class~='not-prose'], [class~='not-prose'] *))::before {
        content: none;
      }
      .email-content :where(blockquote p:last-of-type):not(:where([class~='not-prose'], [class~='not-prose'] *))::after {
        content: none;
      }
    </style>
  </head>
  <body>
    <div class="email-content prose-f">${_content.value}</div>
  </body>
  </html>
  `
);

watch(iframeRef, (iframe) => {
  if (iframe) {
    iframe.onload = () => {
      const emailContent =
        iframe.contentWindow?.document.querySelector(".email-content");
      if (!emailContent) return;

      const parent = emailContent.closest("html");
      if (!parent) return;
      parent.setAttribute("data-theme", dataTheme.value);

      const font = getFontFamily(_content.value);
      if (font) emailContent.classList.add(font);

      iframe.style.height = parent.offsetHeight + 1 + "px";

      // Clicks inside the iframe don't bubble to the parent document, popovers/dropdowns that close on outside-click never fire.
      iframe.contentDocument?.addEventListener("pointerdown", () => {
        document.dispatchEvent(
          new PointerEvent("pointerdown", { bubbles: true })
        );
      });

      // This is to ensure that keyboard shortcuts work even when the iframe is focused. For example, pressing "r" to reply to an email should work even if the user has clicked inside the email content.
      iframe.contentDocument?.addEventListener("keydown", (e) => {
        document.dispatchEvent(
          new KeyboardEvent("keydown", {
            key: e.key,
            code: e.code,
            ctrlKey: e.ctrlKey,
            metaKey: e.metaKey,
            shiftKey: e.shiftKey,
            altKey: e.altKey,
            bubbles: true,
          })
        );
      });

      const replyCollapsers = emailContent.querySelectorAll(".replyCollapser");
      if (replyCollapsers.length) {
        replyCollapsers.forEach((replyCollapser) => {
          replyCollapser.addEventListener("change", () => {
            iframe.style.height = parent.offsetHeight + 1 + "px";
          });
        });
      }
    };
  }
});

watch(dataTheme, (theme) => {
  const html = iframeRef.value?.contentDocument?.documentElement;
  if (html) html.setAttribute("data-theme", theme);
});
</script>
