(() => {
  const start = document.getElementById("start");
  const pause = document.getElementById("pause");
  const stop = document.getElementById("stop");
  const status = document.getElementById("status");
  const error = document.getElementById("error");
  const preview = document.getElementById("preview");
  const download = document.getElementById("download");
  let recorder, stream, chunks = [], objectUrl, maxBytes = 0, failed = false;

  function send(type, data) {
    window.parent.postMessage({ isStreamlitMessage: true, type, ...data }, "*");
  }
  function resize() {
    send("streamlit:setFrameHeight", { height: document.body.scrollHeight + 4 });
  }
  function showError(message) {
    error.textContent = message;
    resize();
  }
  function release(enableStart = true) {
    if (stream) stream.getTracks().forEach(track => track.stop());
    stream = undefined;
    start.disabled = !enableStart;
    pause.disabled = true;
    stop.disabled = true;
    pause.textContent = "⏸ Pause";
  }
  window.addEventListener("message", event => {
    if (event.source !== window.parent || event.data.type !== "streamlit:render") return;
    maxBytes = event.data.args.max_bytes;
    resize();
  });
  start.addEventListener("click", async () => {
    if (objectUrl && !window.confirm("အသံအသစ်ဖမ်းလျှင် ဤနေရာရှိ ယခင်အသံကို ဖယ်ရှားမည်။ Drive သို့မဟုတ် စက်ထဲ သိမ်းပြီးပြီလား။")) {
      return;
    }
    start.disabled = true;
    error.textContent = "";
    if (!navigator.mediaDevices?.getUserMedia || !window.MediaRecorder) {
      showError("ဤ browser တွင် အသံဖမ်းမရပါ။ Chrome သို့မဟုတ် Safari အသစ်ဖြင့် စမ်းပါ။");
      release();
      return;
    }
    try {
      stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const types = ["audio/webm", "audio/mp4", "audio/ogg"];
      const type = types.find(item => MediaRecorder.isTypeSupported(item));
      if (!type) throw new Error("Unsupported recording format");
      recorder = new MediaRecorder(stream, { mimeType: type });
      chunks = [];
      failed = false;
      recorder.addEventListener("dataavailable", event => {
        if (event.data.size) chunks.push(event.data);
      });
      recorder.addEventListener("error", () => {
        failed = true;
        showError("အသံဖမ်းရာတွင် အမှားဖြစ်ပါသည်။ ပြန်ကြိုးစားပါ။");
        release(false);
      });
      recorder.addEventListener("stop", async () => {
        const blob = new Blob(chunks, { type });
        chunks = [];
        release(false);
        if (!blob.size) {
          showError("အသံဖိုင်အလွတ် ဖြစ်နေပါသည်။ ပြန်ဖမ်းပါ။");
          start.disabled = false;
          return;
        }
        if (objectUrl) URL.revokeObjectURL(objectUrl);
        objectUrl = URL.createObjectURL(blob);
        preview.src = objectUrl;
        preview.hidden = false;
        download.href = objectUrl;
        download.download = `worship-recording.${type === "audio/mp4" ? "m4a" : type.split("/")[1]}`;
        download.hidden = false;
        if (failed) {
          showError("အသံဖမ်းရာတွင် အမှားဖြစ်ခဲ့ပါသည်။ ရရှိသည့်အပိုင်းကို အောက်က link ဖြင့် စက်ထဲသိမ်းနိုင်ပါသည်။");
          status.textContent = "Drive သို့ မပို့ရသေးပါ။";
          start.disabled = false;
          return;
        }
        if (blob.size > maxBytes) {
          showError("ဖိုင်အရွယ်အစားကန့်သတ်ချက် ကျော်နေပါသည်။ အောက်က link ဖြင့် စက်ထဲသိမ်းပါ။");
          status.textContent = "Drive သို့ မပို့ရသေးပါ။";
          start.disabled = false;
          return;
        }
        try {
          const header = new TextEncoder().encode(type + "\n");
          const bytes = new Uint8Array(header.length + blob.size);
          bytes.set(header);
          bytes.set(new Uint8Array(await blob.arrayBuffer()), header.length);
          status.textContent = "အသံဖမ်းပြီးပါပြီ။ Drive ထဲသိမ်းရန် ခလုတ်ကို နှိပ်ပါ။";
          send("streamlit:setComponentValue", { value: bytes, dataType: "bytes" });
        } catch {
          showError("အသံဖိုင်ကို app သို့ မပို့နိုင်ပါ။ အောက်က link ဖြင့် စက်ထဲသိမ်းပါ။");
        }
        start.disabled = false;
        resize();
      });
      send("streamlit:setComponentValue", { value: null, dataType: "json" });
      if (objectUrl) URL.revokeObjectURL(objectUrl);
      objectUrl = undefined;
      preview.hidden = true;
      download.hidden = true;
      recorder.start();
      pause.disabled = false;
      stop.disabled = false;
      status.textContent = "အသံဖမ်းနေပါသည်။";
      resize();
    } catch {
      showError("အသံဖမ်းမရပါ။ Browser တွင် microphone ခွင့်ပြုချက်ကို စစ်ပါ။");
      release();
    }
  });
  pause.addEventListener("click", () => {
    if (recorder.state === "recording") {
      recorder.pause();
      pause.textContent = "▶ Resume";
      status.textContent = "ခဏရပ်ထားပါသည်။ Resume ကိုနှိပ်၍ ပြန်ဆက်ပါ။";
    } else if (recorder.state === "paused") {
      recorder.resume();
      pause.textContent = "⏸ Pause";
      status.textContent = "အသံဖမ်းနေပါသည်။";
    }
    resize();
  });
  stop.addEventListener("click", () => {
    stop.disabled = true;
    pause.disabled = true;
    status.textContent = "အသံဖိုင်ကို ပြင်ဆင်နေပါသည်။";
    recorder.stop();
  });
  window.addEventListener("pagehide", release);
  send("streamlit:componentReady", { apiVersion: 1 });
})();
