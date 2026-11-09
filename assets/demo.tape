# The README demo: a swarm builds, asks about a Friday deploy, ships, melts down.
# Re-record from the repository root with:  vhs assets/demo.tape
# then shrink it with the ffmpeg command in the README's development section.
Output assets/demo.gif

Set Shell "zsh"
Set FontSize 13
Set Width 1200
Set Height 720
Set Padding 18
Set Theme "Catppuccin Mocha"
Set TypingSpeed 55ms
Set Framerate 15

Hide
Type "export PS1='$ ' && alias larp='uv run --quiet larp' && uv sync --quiet && clear"
Enter
Sleep 3s
Show

Type 'larp "ship to prod on a friday" --length 10 -n 6 --seed 7'
Sleep 600ms
Enter

# The plan, then work until the agent asks about the Friday deploy; hold it.
Sleep 8s
# Take the recommendation, like everyone does.
Enter
Sleep 11s

Type "ship it"
Sleep 400ms
Enter

# Ship, launch the deploy, watch prod melt down, and catch the "jk".
Sleep 30s
