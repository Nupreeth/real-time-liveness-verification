(function () {
    const body = document.body;
    const frameIntervalMs = Number(body.dataset.frameInterval || "200");
    const verifiedEmail = body.dataset.email || "";
    const verifiedToken = body.dataset.token || "";

    const video = document.getElementById("webcam");
    const statusText = document.getElementById("status-text");
    const earText = document.getElementById("ear-text");
    const openText = document.getElementById("open-text");
    const closedText = document.getElementById("closed-text");
    const progressLabel = document.getElementById("progress-label");
    const progressBar = document.getElementById("progress-bar");

    const canvas = document.createElement("canvas");
    const context = canvas.getContext("2d");

    let stream = null;
    let timerId = null;
    let requestInFlight = false;
    let finished = false;
    let failureCount = 0;
    let startedAt = Date.now();

    async function startWebcam() {
        try {
            stream = await navigator.mediaDevices.getUserMedia({
                video: {
                    facingMode: "user",
                    width: { ideal: 960 },
                    height: { ideal: 540 }
                },
                audio: false
            });
            video.srcObject = stream;
            await video.play();
            statusText.textContent = "Camera active. Keep one centered face and blink naturally.";
            timerId = window.setInterval(processFrame, frameIntervalMs);
        } catch (error) {
            statusText.textContent = "Unable to access webcam. Allow camera permission and retry.";
            finish("failed");
        }
    }

    function captureFrameAsBase64() {
        if (!video.videoWidth || !video.videoHeight) {
            return null;
        }
        canvas.width = video.videoWidth;
        canvas.height = video.videoHeight;
        context.drawImage(video, 0, 0, canvas.width, canvas.height);
        return canvas.toDataURL("image/jpeg", 0.85);
    }

    function updateProgress(payload) {
        let completion = 0;
        if (payload.blink_open_seen) {
            completion += 34;
        }
        if (payload.blink_closed_seen) {
            completion += 33;
        }
        if (payload.blink_reopen_seen) {
            completion += 33;
        }
        if (completion > 100) {
            completion = 100;
        }

        progressBar.style.width = completion + "%";
        progressLabel.textContent = completion + "%";
    }

    function updateStatus(payload) {
        statusText.textContent = payload.message || "Processing frame...";
        openText.textContent = "Open-eye: " + (payload.open_captured ? "captured" : "pending");
        closedText.textContent = "Closed-eye: " + (payload.closed_captured ? "captured" : "pending");

        if (typeof payload.ear === "number") {
            earText.textContent = "EAR: " + payload.ear.toFixed(3);
        } else {
            earText.textContent = "EAR: --";
        }

        updateProgress(payload);
    }

    async function processFrame() {
        if (finished || requestInFlight) {
            return;
        }

        const image = captureFrameAsBase64();
        if (!image) {
            return;
        }

        requestInFlight = true;
        try {
            const response = await fetch("/process_frame", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    image: image,
                    email: verifiedEmail,
                    token: verifiedToken
                })
            });
            const payload = await response.json();
            updateStatus(payload);

            if (!response.ok) {
                throw new Error(payload.message || "Frame processing failed.");
            }

            if (payload.state === "verified" || payload.state === "failed") {
                finish(payload.state);
            }

            failureCount = 0;
        } catch (error) {
            failureCount += 1;
            statusText.textContent = error.message || "Connection issue during frame processing.";

            if (failureCount >= 5 || Date.now() - startedAt > 40000) {
                finish("failed");
            }
        } finally {
            requestInFlight = false;
        }
    }

    function stopStream() {
        if (timerId) {
            window.clearInterval(timerId);
            timerId = null;
        }
        if (stream) {
            stream.getTracks().forEach((track) => track.stop());
            stream = null;
        }
    }

    function finish(state) {
        if (finished) {
            return;
        }
        finished = true;
        stopStream();
        window.location.href = "/result?status=" + encodeURIComponent(state || "failed");
    }

    window.addEventListener("beforeunload", stopStream);
    startWebcam();
})();
