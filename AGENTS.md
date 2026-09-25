# Project conventions

- Use English for repository documentation, UI text, code comments, commit messages, and GitHub project content.
- Communicate with the maintainer in Chinese unless they request another language.
- When explaining how to restart or continue work on the school machine, include the Ubuntu tunnel command:
  `"$HOME/.local/share/vscode-cli/code" tunnel --name insight-ultrasound`.
- Keep inference independent of reference tracking labels. Read labels only in explicitly identified offline evaluation steps; do not replace predicted poses with reference poses.
