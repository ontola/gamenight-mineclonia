# Physical controller check

The automated package test routes scripted host frames. It cannot assess stick
feel or prove that a physical D-pad is comfortable to use.

Run `python controller_check.py --package PACKAGE --seconds 90 --output evidence.json`
while testing the installed game through the real GameNight host. This records
only actual SDL input. It sends no input to games and changes no controller mapping.

For each controller:

1. Join a seat and launch Mineclonia. Confirm your profile name, face and color.
2. Move through the start/pause menu using D-pad and left stick. Focus should move
   between controls; A selects and B returns. No mouse aiming should be required.
3. Walk, look, jump, mine, place, change hotbar slot and open the inventory.
   Check that only your viewport responds, including while another player uses a menu.
4. Use Back to return to GameNight, then resume. Check audio and held-button release.
5. Disconnect and reconnect your pad. Movement should stop immediately and resume
   only for your seat. Repeat after switching profile/seat in the lobby.
6. Repeat at one, two, three and four players when enough physical pads are available.

Record player count, device model, game package hash, actions exercised and any
focus/comfort problems. An enumeration or input log is not a pass for this checklist.
