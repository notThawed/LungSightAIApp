/**
 * How LungSightAI describes AI output. Mirrors shared/ai_labels.py on the web.
 * The models only classify a chest X-ray as positive/negative for pneumonia
 * (and bacterial/viral for positives); never claim more than that.
 */

export const AI_DISCLAIMER =
  'AI decision support only — not a diagnosis. A qualified clinician must review the image and confirm the result.';
