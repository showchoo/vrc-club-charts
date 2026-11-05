// Creator-controlled DJ video-player telemetry probe for a test World.
// Requires Unity + official VRChat Worlds SDK + UdonSharp.
// This code is NOT installed into arbitrary Worlds, does NOT perform unattended
// client access, and never connects to a network endpoint.
//
// Place beside the video-player component in a World YOU OWN or may edit.
// Assign the BaseVRCVideoPlayer in the Inspector; set real World ID and a
// unique run token. Use the Interact method or invoke BeginProbe from a local
// World UI button. Then play a known, permitted TEST VIDEO normally.
// Events are written to the local VRChat client output log.
//
// This is only evidence of player EVENTs and a moving playback clock, not
// proof of audible output, live DJ stream operation, actual screen pixels,
// synchronization, or device functionality across other clients.
using UdonSharp;
using UnityEngine;
using VRC.SDKBase;
using VRC.SDK3.Video.Components.Base;
using VRC.SDK3.Components.Video;

public class VCCDJVideoProbe : UdonSharpBehaviour
{
    [Tooltip("Assign the official VRChat video player on this same GameObject")]
    public BaseVRCVideoPlayer targetPlayer;

    [Tooltip("Actual World ID configured by the creator, not automatically authenticated")]
    public string worldId = "wrld_00000000-0000-0000-0000-000000000000";

    [Tooltip("Unique 8-32 character test token: letters, numbers, _ or -")]
    public string sessionToken = "TESTONLY01";

    [Tooltip("Component identifier: letters, numbers, _ or -, maximum 32 chars")]
    public string componentId = "screen01";

    private bool running = false;
    private int samples = 0;
    private float nextSampleAt = 0f;
    private float beganAt = 0f;
    private const int MaxSamples = 20;

    public override void Interact()
    {
        if (!running) BeginProbe();
        else EndProbe();
    }

    public void BeginProbe()
    {
        if (running) return;
        // Do not record users' names or URLs. Restrict this test to a private,
        // creator-approved instance with only the tester in the room.
        if (VRCPlayerApi.GetPlayerCount() != 1)
        {
            Debug.Log("VCCDJPROBE|privacy_check_failed");
            return;
        }
        if (targetPlayer == null)
        {
            Debug.Log("VCCDJPROBE|unconfigured_player");
            return;
        }
        running = true;
        samples = 0;
        beganAt = Time.realtimeSinceStartup;
        nextSampleAt = beganAt + 1f;
        Emit("begin", -1, 0);
    }

    public void EndProbe()
    {
        if (!running) return;
        Emit("stop", -1, 0);
        running = false;
    }

    public override void OnPlayerJoined(VRCPlayerApi player)
    {
        if (running && VRCPlayerApi.GetPlayerCount() != 1)
        {
            Emit("privacy_stop", -1, 0);
            running = false;
        }
    }

    public override void OnVideoReady()
    {
        if (running) Emit("ready", -1, 0);
    }

    public override void OnVideoStart()
    {
        if (running) Emit("start", -1, 0);
    }

    public override void OnVideoPlay()
    {
        if (running) Emit("play", -1, 0);
    }

    public override void OnVideoPause()
    {
        if (running) Emit("pause", -1, 0);
    }

    public override void OnVideoEnd()
    {
        if (!running) return;
        Emit("end", -1, 0);
        running = false;
    }

    public override void OnVideoError(VideoError videoError)
    {
        if (!running) return;
        Emit("error", -1, (int)videoError);
        running = false;
    }

    private void Update()
    {
        if (!running) return;
        if (VRCPlayerApi.GetPlayerCount() != 1)
        {
            Emit("privacy_stop", -1, 0);
            running = false;
            return;
        }
        if (Time.realtimeSinceStartup - beganAt > 60f)
        {
            EndProbe();
            return;
        }
        if (samples >= MaxSamples || Time.realtimeSinceStartup < nextSampleAt)
        {
            return;
        }
        nextSampleAt = Time.realtimeSinceStartup + 1f;
        samples++;

        // GetTime is a decoder clock, not proof of visible pixels or audio.
        // For live streams GetTime may be unavailable, so the parser returns
        // "inconclusive" rather than falsely declaring function verified.
        float seconds = targetPlayer.GetTime();
        int milliseconds = -1;
        if (seconds >= 0f && seconds <= 36000f)
        {
            milliseconds = (int)(seconds * 1000f);
        }
        Emit("sample", milliseconds, 0);
    }

    private void Emit(string eventName, int videoMilliseconds, int code)
    {
        // Use integer milliseconds, not locale-dependent decimal output.
        // Never include user handles, player URLs, private World contents,
        // or live chat in the telemetry line.
        int elapsedMs = (int)((Time.realtimeSinceStartup - beganAt) * 1000f);
        Debug.Log(
            "VCCDJPROBE|v=1|session=" + sessionToken
            + "|world=" + worldId
            + "|component=" + componentId
            + "|event=" + eventName
            + "|ms=" + elapsedMs
            + "|vms=" + videoMilliseconds
            + "|players=" + VRCPlayerApi.GetPlayerCount()
            + "|code=" + code
        );
    }
}
