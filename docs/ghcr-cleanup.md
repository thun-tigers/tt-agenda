# Alte GHCR-Paket-Versionen loeschen

Erwartete Env-Variablen: `PKG_OWNER` (User oder Org), `PKG_NAME` (Image-Name),
`LATEST_ID` (Version-ID die erhalten bleiben soll).

```bash
gh api \
  -H "Accept: application/vnd.github+json" \
  /users/$PKG_OWNER/packages/container/$PKG_NAME/versions \
  --paginate \
  | jq ".[] | select(.id != ${LATEST_ID}) | .id" \
  | while read ID; do
      echo "Deleting version $ID"
      gh api \
        --method DELETE \
        -H "Accept: application/vnd.github+json" \
        /users/$PKG_OWNER/packages/container/$PKG_NAME/versions/$ID
    done
```
