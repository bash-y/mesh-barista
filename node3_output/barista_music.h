// Mesh Barista: tunes for the passive buzzers on Nodes 1 and 2.
// The master copy lives in dashboard_src/; build_assets.py copies it into each sketch folder.
//
// A passive buzzer needs a square wave at the note's pitch (a steady HIGH or LOW is silent), so notes
// are played with the ESP32's LEDC PWM. Nothing here blocks: call musicUpdate() every loop() and it
// works out which note should be sounding from the time the tune started. Node 1 and Node 2 start
// the pour tune when the pump starts, so Node 1's bass and Node 2's melody stay together.
//
// Pour tune: an original smooth-jazz loop in F major, ii-V-I-VI (Gm7 | C7 | Fmaj7 | D7), swung.
// Time unit: one tick = a triplet eighth note. Swung eighths are 2 + 1 ticks, a quarter note is 3.
//
// Include it once, from the sketch. The sketch must define BUZZER_PIN and BUZZER_ON first.

struct Note { uint8_t midi; uint8_t ticks; };  // midi 0 = rest. 60 = middle C, 69 = A 440 Hz

const unsigned long MUSIC_TICK_MS = 179;  // 112 beats per minute, 3 ticks per beat
const float         MUSIC_LEGATO  = 0.85; // each note sounds for this part of its length, then a tiny gap

// Node 2: melody (octave 5, where a small buzzer is loudest)
const Note TUNE_MELODY[] = {
  {74, 2}, {77, 1}, {81, 3}, {79, 2}, {77, 1}, {74, 3},  // Gm7:   D F A  G F D
  {76, 2}, {79, 1}, {82, 2}, {81, 1}, {79, 3}, {76, 3},  // C7:    E G Bb A G E
  {81, 6},           {79, 2}, {76, 1}, {72, 3},          // Fmaj7: A (held)  G E C
  {78, 2}, {81, 1}, {84, 2}, {82, 1}, {81, 3}, { 0, 3},  // D7:    F# A C Bb A, rest
};

// Node 1: walking bass, quarter notes, chromatic steps into each new chord
const Note TUNE_BASS[] = {
  {55, 3}, {57, 3}, {58, 3}, {59, 3},  // Gm7:   G A Bb B
  {60, 3}, {58, 3}, {55, 3}, {54, 3},  // C7:    C Bb G Gb
  {53, 3}, {57, 3}, {60, 3}, {61, 3},  // Fmaj7: F A C C#
  {62, 3}, {60, 3}, {57, 3}, {56, 3},  // D7:    D C A Ab  (-> G, the top again)
};

// Node 2: "drink ready", a quick Fmaj7 run up to a held E
const Note TUNE_READY[] = { {72, 1}, {76, 1}, {77, 1}, {81, 1}, {84, 1}, {88, 5} };

// Node 2: boot chime
const Note TUNE_BOOT[] = { {77, 1}, {81, 1}, {84, 3} };

#define TUNE(t) t, (int)(sizeof(t) / sizeof(t[0]))

const Note*   musicNotes = nullptr;
int           musicCount = 0;
bool          musicLoop  = false;
unsigned long musicStart = 0;
bool          buzzAttached = false;
uint32_t      buzzFreq     = 0;

// ---------- the buzzer itself ----------
void buzzerOff() {
  if (buzzAttached) { ledcDetach(BUZZER_PIN); buzzAttached = false; }
  pinMode(BUZZER_PIN, OUTPUT);
  digitalWrite(BUZZER_PIN, !BUZZER_ON);  // idle level: no current through the buzzer
  buzzFreq = 0;
}

void buzzerTone(uint32_t hz) {
  if (hz == buzzFreq) return;
  if (!hz) { buzzerOff(); return; }
  if (!buzzAttached) buzzAttached = ledcAttach(BUZZER_PIN, hz, 10);
  ledcWriteTone(BUZZER_PIN, hz);  // square wave, 50 % duty
  buzzFreq = hz;
}

uint32_t midiHz(uint8_t m) { return m ? (uint32_t)(440.0f * powf(2.0f, (m - 69) / 12.0f) + 0.5f) : 0; }

// ---------- tunes ----------
void musicPlay(const Note* notes, int count, bool loop, unsigned long startMs) {
  musicNotes = notes;
  musicCount = count;
  musicLoop  = loop;
  musicStart = startMs;
}

void musicStop() { musicNotes = nullptr; }
bool musicPlaying() { return musicNotes != nullptr; }
bool musicPlaying(const Note* notes) { return musicNotes == notes; }

// The frequency the current tune wants right now (0 = silent). Ends a one-shot tune when it is over.
uint32_t musicNow(unsigned long now) {
  if (!musicNotes) return 0;
  int total = 0;
  for (int i = 0; i < musicCount; i++) total += musicNotes[i].ticks;
  unsigned long t = now - musicStart, len = total * MUSIC_TICK_MS;
  if (t >= len) {
    if (!musicLoop) { musicStop(); return 0; }
    t %= len;
  }
  for (int i = 0; i < musicCount; i++) {
    unsigned long d = musicNotes[i].ticks * MUSIC_TICK_MS;
    if (t < d) return t < d * MUSIC_LEGATO ? midiHz(musicNotes[i].midi) : 0;
    t -= d;
  }
  return 0;
}

// ---------- coffee machine gurgle ----------
// Not a tune: random bubbles. Each bubble is a short "bloop" whose pitch slides (mostly up, like a
// bubble bursting), with a little wobble. Bubbles come in clusters with short gaps, and clusters are
// separated by longer pauses, which is what makes it sound like a machine sputtering, not a beeper.
bool          gurgleOn = false;
unsigned long bubStart = 0, bubLen = 0, bubGapUntil = 0;
int           bubFrom = 0, bubTo = 0, bubLeft = 0;

void gurgleStart() { gurgleOn = true; bubLeft = 0; bubGapUntil = 0; bubLen = 0; }
void gurgleStop()  { gurgleOn = false; }

uint32_t gurgleNow(unsigned long now) {
  if (!gurgleOn) return 0;
  if (now - bubStart < bubLen) {  // inside a bubble: slide from bubFrom to bubTo, curving like a bloop
    float p = (float)(now - bubStart) / bubLen;
    int hz = bubFrom + (bubTo - bubFrom) * p * p + (int)((now / 4 * 2654435761UL) % 61) - 30;  // wobble, steps of 4 ms
    return (uint32_t)max(80, hz / 10 * 10);
  }
  if (now < bubGapUntil) return 0;  // between bubbles
  if (bubLeft <= 0) bubLeft = random(2, 8);  // a new cluster
  bubLeft--;
  bubStart = now;
  bubLen   = random(25, 75);
  bubFrom  = random(170, 420);
  bubTo    = random(4) ? bubFrom + random(120, 380) : bubFrom - random(40, 110);  // 1 in 4 slides down
  bubGapUntil = now + bubLen + (bubLeft > 0 ? random(8, 60) : random(90, 350));
  return bubFrom;
}

// Call every loop(). An alarm or a test beep (alarmHz > 0) always wins over music and the gurgle.
void musicUpdate(unsigned long now, uint32_t alarmHz) {
  uint32_t music = musicNow(now);
  if (!music) music = gurgleNow(now);
  buzzerTone(alarmHz ? alarmHz : music);
}
