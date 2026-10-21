import { io } from "socket.io-client";
import { socketio_port } from "../../../../sites/common_site_config.json";

// extend window object
declare global {
  interface Window {
    site_name: string;
  }
}

export function initSocket() {
  let host = window.location.hostname;
  let siteName = window.site_name || host;
  // Production builds are served behind nginx, which proxies /socket.io on the page's own
  // origin; only the Vite dev server needs the separate socketio port.
  let url = `${window.location.origin}/${siteName}`;
  if (import.meta.env.DEV) {
    let port = window.location.port ? `:${socketio_port}` : "";
    let protocol = port ? "http" : "https";
    url = `${protocol}://${host}${port}/${siteName}`;
  }

  const socket = io(url, {
    withCredentials: true,
    reconnectionAttempts: 5,
  });

  return socket;
}

export const socket = initSocket();
