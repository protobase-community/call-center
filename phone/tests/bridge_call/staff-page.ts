// A staff member in the browser, for run.sh: joins the call on a phone call's record through
// @protobase/client/calls, speaks lines into a WebAudio microphone, and records what the caller's
// member sends: the phone side of the call, through the bridge. driver.ts bundles it into a page of
// the app, so the socket carries the staff member's session cookie.
import { joinCall, type Call, type CallTrack } from '@protobase/client/calls'
import { phoneCallSocketPath } from '../../../config/phone_calls/call-address'

let call: Call | undefined
const context = new AudioContext({ sampleRate: 48000 })
const microphone = context.createMediaStreamDestination()
// a silent source keeps the track sending, as a real microphone does between words
const silence = context.createConstantSource()
silence.offset.value = 0
silence.connect(microphone)
silence.start()
const events: { at: number; kind: string; detail?: string }[] = []
const log = (kind: string, detail?: string) => events.push({ at: Date.now(), kind, ...(detail && { detail }) })

// Headless Chromium decodes remote audio only while an element plays it (it runs with
// --mute-audio), and MediaRecorder records it: the caller's side is recorded whole.
let recorder: MediaRecorder | undefined
let recorded: MediaStreamTrack | undefined
let chunks: Blob[] = []

const listen = (tracks: CallTrack[]) => {
  const caller = tracks.find((track) => track.member === 'caller' && track.kind === 'audio' && track.track)?.track
  if (!caller || caller === recorded) return
  recorded = caller
  recorder?.stop()
  chunks = []
  document.querySelectorAll('audio').forEach((element) => element.remove())
  document.body.append(Object.assign(document.createElement('audio'), { autoplay: true, srcObject: new MediaStream([caller]) }))
  recorder = new MediaRecorder(new MediaStream([caller]))
  const own = chunks
  recorder.ondataavailable = (event) => own.push(event.data)
  recorder.start(1000)
  log('recording', caller.id)
}

const staff = {
  join: async (phoneCall: number) => {
    // a granted microphone lets Chromium offer its host addresses as candidates, as in a real call
    for (const track of (await navigator.mediaDevices.getUserMedia({ audio: true })).getTracks()) track.stop()
    call = await joinCall({
      url: phoneCallSocketPath(phoneCall),
      onTracks: listen,
      onMembers: (members) => log('members', members.map((m) => m.member).join(',')),
      onState: (state) => log('state', state.state),
    })
    await context.resume()
    await call.publish({ microphone: microphone.stream.getAudioTracks()[0]! })
    log('joined')
  },
  /** Plays a line into the microphone; resolves when it has played. */
  say: async (name: string, base64: string) => {
    const bytes = Uint8Array.from(atob(base64), (c) => c.charCodeAt(0))
    const buffer = await context.decodeAudioData(bytes.buffer)
    const source = context.createBufferSource()
    source.buffer = buffer
    source.connect(microphone)
    log('said_started', name)
    source.start()
    await new Promise((resolve) => (source.onended = resolve))
    log('said_stopped', name)
  },
  /** Everything received from the caller's member since it was heard, as base64 webm. */
  recording: async () => {
    if (!recorder) return ''
    const stopped = new Promise((resolve) => (recorder!.onstop = resolve))
    recorder.stop()
    await stopped
    const bytes = new Uint8Array(await new Blob(chunks).arrayBuffer())
    let binary = ''
    for (const b of bytes) binary += String.fromCharCode(b)
    return btoa(binary)
  },
  leave: () => {
    call?.leave()
    log('left')
  },
  events: () => events,
}

declare global {
  interface Window {
    staff: typeof staff
  }
}
window.staff = staff
