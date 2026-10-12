# Flag of Clairvoyance

- **Challenge author:** abcjr
- **Category:** Miscellaneous
- **Flag format:** `DCTF{string}`
- **Challenge:** sea-of-theft / Flag of Clairvoyance

## Challenge description and initial analysis

The prompt hinted that “not all is as it seems.” The supplied browser game rendered its world in a canvas, so DOM inspection alone could not reveal hidden text.

## The short version

The challenge is a small pirate MMO rendered inside an HTML canvas. The flag is split into two pieces:

1. The game occasionally broadcasts this message:

   ```text
   The waves whisper: DCTF{W4llh4ck1
   ```

2. The rest of the flag is drawn as individual letters **behind a giant rectangle labelled `WALL`**:

   ```text
   N6_1s_s0_m3Ta}
   ```

Putting the two parts together gives:

```text
DCTF{W4llh4ck1N6_1s_s0_m3Ta}
```

In normal English, the flag says **“wallhacking is so meta”**. That is a pretty good summary of the solution!

---

## First look at the game

Opening the site presents what looks like a real multiplayer pirate game. We can choose a randomly generated pirate name, sail around, shoot other ships, collect treasure, and appear on a leaderboard.

At first I looked through the page source for the usual easy wins: hidden HTML comments, JavaScript variables, API responses, and strings containing `DCTF`. That did not reveal the flag. The important reason is that almost the entire game is implemented in **WebAssembly** and drawn onto one HTML `<canvas>`.

For a non-web person, a canvas is basically a blank sheet of pixels. The browser does not keep a convenient HTML element for every ship, message, wall, or letter. The game just issues commands such as:

```text
draw this image here
draw this rectangle there
draw this text on top
```

That makes normal DOM inspection much less useful. It also creates an interesting weakness: if the game draws secret text and then paints a wall over it, the text still existed for a moment during the drawing process.

The clue **“Not all is as it seems”** and the name **“Flag of Clairvoyance”** both point toward seeing something that the normal player is not supposed to see.

## Watching what the canvas draws

The browser exposes its text-drawing function as:

```javascript
CanvasRenderingContext2D.prototype.fillText
```

JavaScript lets us replace that function with a wrapper. Our wrapper records every piece of text and then calls the real function so the game continues normally.

I installed the following hook before pressing **Play**:

```javascript
(() => {
    window.drawnText = [];

    const realFillText = CanvasRenderingContext2D.prototype.fillText;

    CanvasRenderingContext2D.prototype.fillText = function (text, x, y, ...rest) {
        const transform = this.getTransform();
        const point = transform.transformPoint(new DOMPoint(x, y));

        const entry = {
            text: String(text),
            x: point.x,
            y: point.y,
            font: this.font,
            fill: String(this.fillStyle)
        };

        window.drawnText.push(entry);

        if (entry.text.includes("DCTF") ||
            entry.text === "WALL" ||
            entry.font.includes("46px")) {
            console.log(entry);
        }

        return realFillText.call(this, text, x, y, ...rest);
    };
})();
```

This is like placing a security camera immediately before the game's paintbrush. Even if another object covers the text one millisecond later, the hook has already saved it.

### The first half

After joining a game and sailing for a little while, the hook caught this global notification:

```text
The waves whisper: DCTF{W4llh4ck1
```

To make sure this was not a browser-rendering mistake, I also checked the underlying binary WebSocket message. Its relevant bytes were:

```text
84 01 09 22 21 54 68 65 20 77 61 76 65 73 20 77 68 69
73 70 65 72 3a 20 44 43 54 46 7b 57 34 6c 6c 68 34 63
6b 31
```

The ASCII portion decodes exactly to:

```text
The waves whisper: DCTF{W4llh4ck1
```

There was no closing brace and no remaining text in that packet. This was therefore only the beginning of the flag, not the entire answer.

## Lying about the size of our screen

The game uses a WebSocket connection to exchange compact binary messages with the server. One of the client messages tells the server the size of our viewport. The format is:

```text
04 <width as little-endian u16> <height as little-endian u16>
```

For example, a 1280 by 757 viewport is sent as:

```text
04 00 05 f5 02
```

The server uses that size to decide which nearby objects should be sent to the browser. This is a normal optimization: there is no reason to send a player objects that are thousands of pixels outside their screen.

However, the server trusted the dimensions supplied by the client. I captured the game's socket by wrapping the WebSocket constructor before joining:

```javascript
(() => {
    const RealWebSocket = window.WebSocket;

    window.WebSocket = class extends RealWebSocket {
        constructor(...args) {
            super(...args);
            window.gameSocket = this;
        }
    };
})();
```

Once connected, I claimed that my viewport was `65535 × 65535`, the largest size that fits in two unsigned 16-bit integers:

```javascript
gameSocket.send(Uint8Array.of(
    0x04,             // viewport message
    0xff, 0xff,       // width  = 65535
    0xff, 0xff        // height = 65535
));
```

The server accepted it and sent many objects that should have been far outside the normal view. In gaming terms, this is basically a crude **wallhack**: the client asks to know about far more of the world than it should.

## The text behind the wall

Among the newly received objects were unusually large individual characters. They used this font:

```text
900 46px ui-monospace, monospace
```

The characters were not sent as one convenient string. Each was its own world object with a position. I filtered the captured `fillText` calls, removed the duplicate shadow/glow pass, grouped characters with roughly the same Y coordinate, and sorted each group from left to right.

Conceptually, the extraction looks like this:

```javascript
const interesting = drawnText
    .filter(x => x.font.includes("900 46px"))
    .sort((a, b) => a.y - b.y || a.x - b.x);

console.table(interesting);
```

There were several decoy groups spelling:

```text
TRY HARDER!
```

The real group was placed around world coordinates `x = 820..1756`, `y = 760`. Its characters, in X-coordinate order, were:

| X | Character |
|---:|:---:|
| 820 | `N` |
| 892 | `6` |
| 964 | `_` |
| 1036 | `1` |
| 1108 | `s` |
| 1180 | `_` |
| 1252 | `s` |
| 1324 | `0` |
| 1396 | `_` |
| 1468 | `m` |
| 1540 | `3` |
| 1612 | `T` |
| 1684 | `a` |
| 1756 | `}` |

That spells:

```text
N6_1s_s0_m3Ta}
```

The capitalization matters: the first `N` and the `T` in `m3Ta` are uppercase.

Immediately after drawing these characters, the renderer draws a large opaque rectangle and writes `WALL` over it. That is why a normal player cannot read the characters even when sailing to the correct location—the browser paints the answer and then covers it.

*Archive note: the wall screenshot was removed during storage cleanup; the intercepted characters and positions are preserved above.*

This also explains why recording `fillText` was more useful than taking screenshots. A screenshot only contains the final painted frame, after the wall has covered the answer. The hook records the drawing operations in the order they happen.

## Building the flag

The broadcast gave us:

```text
DCTF{W4llh4ck1
```

The hidden characters behind the wall gave us:

```text
N6_1s_s0_m3Ta}
```

Concatenating them without adding or removing anything produces:

```text
DCTF{W4llh4ck1N6_1s_s0_m3Ta}
```

Reading the leetspeak makes the joke clear:

```text
W4llh4ck1N6  -> WALLHACKING
1s           -> IS
s0           -> SO
m3Ta         -> META
```

## Flag

```text
DCTF{W4llh4ck1N6_1s_s0_m3Ta}
```

## Takeaways

- A canvas hides its contents from the normal HTML inspector, but its drawing functions can still be hooked.
- Something being invisible in the final frame does not mean it was never rendered.
- Multiplayer clients should not be trusted when they report values such as viewport size.
- When a partial flag is missing its closing brace, it may genuinely be only one piece of a larger puzzle.
- Decoys saying `TRY HARDER!` are annoying, but they are also a good sign that you are looking in the intended place.

## Reproduction and files

Run [`canvas_hook.js`](canvas_hook.js) in the browser console before joining the game. After joining, call `expandViewport()` and inspect `hiddenText()`; the hook records draw calls before the wall covers the lettering. The intercepted draw calls document the occlusion; the screenshot was omitted for storage. The hook is specific to the challenge game and is not a general-purpose browser exploit.
