/**
 * Accessibility Audio Playback & Speech Recognition utilities for Project Amaanat.
 * 
 * Features:
 * - Plays edge-tts generated MP3 files from /audio/*.mp3
 * - Graceful fallback to browser SpeechSynthesis API (ur-PK) if file missing
 * - Chained digit audio playback for phone and CNIC numbers
 * - Web Speech recognition for Urdu (haan / nahin / digits)
 */

export async function playAudioClip(clipName: string, fallbackUrduText?: string): Promise<void> {
  const audioUrl = `/audio/${clipName}.mp3`;
  return new Promise((resolve) => {
    const audio = new Audio(audioUrl);
    audio.onended = () => resolve();
    audio.onerror = () => {
      // Fallback to SpeechSynthesis
      if (fallbackUrduText && 'speechSynthesis' in window) {
        const utterance = new SpeechSynthesisUtterance(fallbackUrduText);
        utterance.lang = 'ur-PK';
        utterance.onend = () => resolve();
        utterance.onerror = () => resolve();
        window.speechSynthesis.speak(utterance);
      } else {
        resolve();
      }
    };
    audio.play().catch(() => {
      // Autoplay policy or error fallback
      if (fallbackUrduText && 'speechSynthesis' in window) {
        const utterance = new SpeechSynthesisUtterance(fallbackUrduText);
        utterance.lang = 'ur-PK';
        utterance.onend = () => resolve();
        utterance.onerror = () => resolve();
        window.speechSynthesis.speak(utterance);
      } else {
        resolve();
      }
    });
  });
}

/**
 * Plays a sequence of digits one by one using chained audio clips.
 */
export async function playChainedDigits(digits: string): Promise<void> {
  const cleanDigits = digits.replace(/\D/g, '');
  for (const char of cleanDigits) {
    await playAudioClip(`digit_${char}`, char);
    await new Promise((r) => setTimeout(r, 120)); // brief pause
  }
}

/**
 * Initializes Urdu Web Speech API listener if available in browser.
 */
export function startUrduSpeechRecognition(
  onRecognized: (text: string) => void,
  onError?: (err: any) => void
): { stop: () => void } | null {
  const SpeechRecognition =
    (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition;

  if (!SpeechRecognition) {
    return null;
  }

  try {
    const recognition = new SpeechRecognition();
    recognition.lang = 'ur-PK';
    recognition.continuous = false;
    recognition.interimResults = false;

    recognition.onresult = (event: any) => {
      const transcript = event.results[0][0].transcript.trim().toLowerCase();
      onRecognized(transcript);
    };

    if (onError) {
      recognition.onerror = onError;
    }

    recognition.start();
    return {
      stop: () => {
        try {
          recognition.stop();
        } catch {}
      },
    };
  } catch (err) {
    if (onError) onError(err);
    return null;
  }
}
