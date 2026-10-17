/**
 * How long a code can be typed. The backend's `game/codes.py` knows the kinds
 * by length (a game id six, a seat code seven, a participant code eight when
 * the study app is on); the input only has to hold the longest of them.
 */
export const CODE_MAX_LENGTH = 7;
export const PARTICIPANT_CODE_LENGTH = 8;

export function codeMaxLength(studies: boolean): number {
  return studies ? PARTICIPANT_CODE_LENGTH : CODE_MAX_LENGTH;
}
