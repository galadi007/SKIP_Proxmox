# skip-capability-sdk

Schnittstelle zwischen dem `capability-operator` und den Capability-Plugins
unter `plugins/capabilities/`. Enthält `Capability` (Protocol), `Claim`,
`Binding`, `SecretRef`, die Fehlertypen und die Entry-Point-Gruppe
`skip.capabilities`. Keine Laufzeitabhängigkeiten, insbesondere kein `kopf`.

Wie ein Plugin aufgebaut ist, beschreibt
[`apps/capability-operator/README.md`](../../apps/capability-operator/README.md).
