// Mêmes jetons que frontend/style.css, pour que l'app mobile ne soit pas un
// produit visuellement à part de la console web CrimTrack.
export const colors = {
  ink: "#10141a",
  panel: "#171d26",
  panel2: "#1d2531",
  border: "#2a3342",
  paper: "#eeeadf",
  text: "#e8e6de",
  textDim: "#929aa8",
  textFaint: "#5c6577",
  seal: "#c2703d",
  sealDim: "#8a5030",
  info: "#5b93ab",
  ok: "#5c9268",
  warn: "#c9a227",
  danger: "#bd4d3f",
};

export const radius = 3;

// Newsreader/Inter/IBM Plex Mono ne sont pas embarquables sans étape de
// build de polices custom en RN — à ajouter via `expo-font` quand le projet
// passe au-delà du scaffold. En attendant, on documente l'intention pour
// que le choix ne se perde pas.
export const fonts = {
  display: "System", // cible: Newsreader
  sans: "System", // cible: Inter
  mono: "monospace", // cible: IBM Plex Mono
};

export const graviteColor = (gravite) => {
  switch (gravite) {
    case "critique":
    case "haute":
      return colors.danger;
    case "moyenne":
      return colors.warn;
    default:
      return colors.ok;
  }
};
