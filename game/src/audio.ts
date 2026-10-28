export interface Ear {
  shot: () => void
  boom: () => void
  card: () => void
  die: () => void
  win: () => void
}

export function createEar(): Ear {
  let context: AudioContext | null = null
  let lastShot = 0

  function audio(): AudioContext | null {
    const Ctx = window.AudioContext
    if (!Ctx) return null
    context ??= new Ctx()
    if (context.state === 'suspended') void context.resume()
    return context
  }

  function tone(freq: number, duration: number, gain: number, type: OscillatorType, when = 0): void {
    const ctx = audio()
    if (!ctx) return
    const start = ctx.currentTime + when
    const osc = ctx.createOscillator()
    const amp = ctx.createGain()
    osc.type = type
    osc.frequency.value = freq
    amp.gain.setValueAtTime(gain, start)
    amp.gain.exponentialRampToValueAtTime(0.001, start + duration)
    osc.connect(amp)
    amp.connect(ctx.destination)
    osc.start(start)
    osc.stop(start + duration + 0.02)
  }

  return {
    shot() {
      const now = performance.now()
      if (now - lastShot < 70) return
      lastShot = now
      tone(720, 0.045, 0.03, 'square')
    },
    boom() {
      tone(90, 0.28, 0.07, 'sawtooth')
    },
    card() {
      tone(440, 0.07, 0.04, 'triangle')
      tone(660, 0.09, 0.03, 'triangle', 0.06)
    },
    die() {
      tone(140, 0.35, 0.07, 'sine')
      tone(70, 0.5, 0.06, 'triangle', 0.05)
    },
    win() {
      tone(392, 0.12, 0.05, 'triangle')
      tone(523, 0.14, 0.05, 'triangle', 0.1)
      tone(659, 0.22, 0.05, 'triangle', 0.2)
    },
  }
}
