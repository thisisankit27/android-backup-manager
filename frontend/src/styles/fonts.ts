/**
 * Typefaces, bundled rather than fetched.
 *
 * The landing page pulls Archivo and IBM Plex from Google Fonts. The app
 * cannot do that for two reasons: it has to work with no internet at all,
 * and it tells people nothing leaves their machine — a webfont request on
 * every launch would quietly make that untrue.
 *
 * Only the weights the design actually uses are imported, and only the
 * latin subsets, which keeps this at roughly 150 KB of woff2 inside the
 * bundle instead of several megabytes of every script and weight.
 */

// Archivo — headings.
import "@fontsource/archivo/latin-700.css";
import "@fontsource/archivo/latin-800.css";

// IBM Plex Sans — body and UI.
import "@fontsource/ibm-plex-sans/latin-400.css";
import "@fontsource/ibm-plex-sans/latin-500.css";
import "@fontsource/ibm-plex-sans/latin-600.css";

// IBM Plex Mono — paths, hashes, sizes, counts. Anything the user might
// compare character by character.
import "@fontsource/ibm-plex-mono/latin-400.css";
import "@fontsource/ibm-plex-mono/latin-500.css";
