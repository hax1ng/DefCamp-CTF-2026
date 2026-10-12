/* Install in the browser console before joining the challenge game. */
(() => {
  const OriginalWebSocket = window.WebSocket;
  window.WebSocket = class extends OriginalWebSocket {
    constructor(...args) {
      super(...args);
      window.gameSocket = this;
    }
  };

  const originalFillText = CanvasRenderingContext2D.prototype.fillText;
  window.drawnText = [];

  CanvasRenderingContext2D.prototype.fillText = function (text, x, y, ...rest) {
    const point = this.getTransform().transformPoint(new DOMPoint(x, y));
    const entry = {
      text: String(text),
      x: point.x,
      y: point.y,
      font: this.font,
    };

    if (entry.text.includes("DCTF") || entry.text === "WALL" ||
        entry.font.includes("46px")) {
      window.drawnText.push(entry);
      console.log(entry);
    }
    return originalFillText.call(this, text, x, y, ...rest);
  };

  window.expandViewport = () => {
    if (!window.gameSocket || window.gameSocket.readyState !== WebSocket.OPEN) {
      throw new Error("Join the game before expanding the viewport");
    }
    // Message 0x04: two little-endian unsigned 16-bit viewport dimensions.
    window.gameSocket.send(Uint8Array.of(0x04, 0xff, 0xff, 0xff, 0xff));
  };

  window.hiddenText = () => {
    const seen = new Set();
    const rows = window.drawnText.filter(({ font }) => font.includes("46px"))
      .filter(({ text, x, y }) => {
        const key = `${text}:${Math.round(x)}:${Math.round(y)}`;
        if (seen.has(key)) return false;
        seen.add(key);
        return true;
      })
      .sort((a, b) => a.y - b.y || a.x - b.x);
    console.table(rows);
    return rows;
  };
})();
