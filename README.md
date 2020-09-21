This repo is used for automatic deployment of https://doegox.github.io/rfidpics

It's based on PhotoFloat by Jason A. Donenfeld, see original [README](README-PhotoFloat.md)

If you want to contribute with pictures, see https://github.com/doegox/rfidpics

How this site works:

* Engine expects images in `web/albums`
* `web/albums` content is maintained at https://github.com/doegox/rfidpics
* When a commit is pushed to master on https://github.com/doegox/rfidpics, a Github Action comes into play, it's YAML is here: https://github.com/doegox/rfidpics/blob/master/.github/workflows/workflow.yml and it publishes the site under https://github.com/doegox/rfidpics/tree/gh-pages
* https://github.com/doegox/rfidpics Settings / GitHub Pages is activated with `gh-pages` serving `/ (root)`

Note that a commit against rfidpics-engine will not trigger an action, last job of https://github.com/doegox/rfidpics must be re-run manually.
