# XP 8 build examples and lookup tables

Companion to SKILL.md. Three things live here, and only here:

1. The full **`xplibs.*` alias tables** (every Enonic library and API the catalog provides).
2. **Worked `build.gradle` examples** for site apps and TS apps with custom `dev` tasks.
3. **TypeScript wiring** (`@enonic-types/*` packages and `tsconfig.json` paths).

Everything else about the XP 8 build (settings plugin, `app { }` block, `gradle.properties`, Gradle wrapper, third-party`libs.versions.toml`
pattern) lives in SKILL.md.

## 1. `xplibs.*` alias tables

The settings plugin (`com.enonic.xp.settings`) supplies a Gradle version catalog `xplibs` covering every `com.enonic.xp:` artifact. Two
namespaces:

- **`xplibs.api.*`** — Java/OSGi APIs (`com.enonic.xp:*-api`). Alias drops the `-api` suffix.
- **`xplibs.*`** — JS-callable libraries (`com.enonic.xp:lib-*`). Alias drops the `lib-` prefix.

All aliases pin to the single `xpVersion` resolved from `gradle.properties`. **If `xpVersion` is missing, the catalog isn't created at all
** — every `xplibs.*` reference fails to resolve.

Tables verified against the settings plugin source (`enonic/xp-gradle-plugin:src/main/java/com/enonic/gradle/xp/SettingsPlugin.java`).

### API aliases (`xplibs.api.*`)

| XP 7 coordinate                         | XP 8 alias          |
|-----------------------------------------|---------------------|
| `com.enonic.xp:core-api:${xpVersion}`   | `xplibs.api.core`   |
| `com.enonic.xp:script-api:${xpVersion}` | `xplibs.api.script` |
| `com.enonic.xp:web-api:${xpVersion}`    | `xplibs.api.web`    |
| `com.enonic.xp:admin-api:${xpVersion}`  | `xplibs.api.admin`  |
| `com.enonic.xp:portal-api:${xpVersion}` | `xplibs.api.portal` |
| `com.enonic.xp:jaxrs-api:${xpVersion}`  | `xplibs.api.jaxrs`  |

### Library aliases (`xplibs.*`)

| XP 7 coordinate                            | XP 8 alias         |
|--------------------------------------------|--------------------|
| `com.enonic.xp:lib-admin:${xpVersion}`     | `xplibs.admin`     |
| `com.enonic.xp:lib-app:${xpVersion}`       | `xplibs.app`       |
| `com.enonic.xp:lib-auditlog:${xpVersion}`  | `xplibs.auditlog`  |
| `com.enonic.xp:lib-auth:${xpVersion}`      | `xplibs.auth`      |
| `com.enonic.xp:lib-cluster:${xpVersion}`   | `xplibs.cluster`   |
| `com.enonic.xp:lib-common:${xpVersion}`    | `xplibs.common`    |
| `com.enonic.xp:lib-content:${xpVersion}`   | `xplibs.content`   |
| `com.enonic.xp:lib-context:${xpVersion}`   | `xplibs.context`   |
| `com.enonic.xp:lib-event:${xpVersion}`     | `xplibs.event`     |
| `com.enonic.xp:lib-export:${xpVersion}`    | `xplibs.export`    |
| `com.enonic.xp:lib-grid:${xpVersion}`      | `xplibs.grid`      |
| `com.enonic.xp:lib-i18n:${xpVersion}`      | `xplibs.i18n`      |
| `com.enonic.xp:lib-io:${xpVersion}`        | `xplibs.io`        |
| `com.enonic.xp:lib-mail:${xpVersion}`      | `xplibs.mail`      |
| `com.enonic.xp:lib-node:${xpVersion}`      | `xplibs.node`      |
| `com.enonic.xp:lib-portal:${xpVersion}`    | `xplibs.portal`    |
| `com.enonic.xp:lib-project:${xpVersion}`   | `xplibs.project`   |
| `com.enonic.xp:lib-repo:${xpVersion}`      | `xplibs.repo`      |
| `com.enonic.xp:lib-scheduler:${xpVersion}` | `xplibs.scheduler` |
| `com.enonic.xp:lib-schema:${xpVersion}`    | `xplibs.schema`    |
| `com.enonic.xp:lib-task:${xpVersion}`      | `xplibs.task`      |
| `com.enonic.xp:lib-value:${xpVersion}`     | `xplibs.value`     |
| `com.enonic.xp:lib-vhost:${xpVersion}`     | `xplibs.vhost`     |
| `com.enonic.xp:lib-websocket:${xpVersion}` | `xplibs.websocket` |

If a `com.enonic.xp:*` library isn't in this list, fall back to the full Maven coordinate. Third-party libraries (`com.enonic.lib:*`) are
never in this catalog — see SKILL.md for the `gradle/libs.versions.toml` pattern.

**Notable exclusion:** `com.enonic.xp:testing` is NOT in the catalog (it's neither a `lib-*` library nor an `*-api`). When migrating XP 7
dependencies, keep its `testImplementation` declaration as the full coord — `xplibs.testing` does not resolve:

```groovy
// XP 8 — keep the full coordinate, no xplibs.* alias exists
testImplementation "com.enonic.xp:testing:${xpVersion}"
```

## 2. Worked `build.gradle` examples

### Example A — site app with third-party libs and a version catalog (`app-superhero-blog`)

Verified against the `app-superhero-blog` reference. Third-party libs (`lib-thymeleaf`, `lib-xslt`, `lib-asset`) are declared in
`gradle/libs.versions.toml` and referenced as `libs.<alias>`:

```groovy
plugins {
    id 'maven-publish'
    id 'com.enonic.defaults' version '2.1.6'
    id 'com.enonic.xp.app'
}

repositories {
    mavenLocal()
    mavenCentral()
    xp.enonicRepo( 'dev' )
}

dependencies {
    include xplibs.content
    include xplibs.context
    include xplibs.portal
    include xplibs.auth
    include xplibs.project
    include xplibs.cluster
    include xplibs.export
    include xplibs.i18n
    include xplibs.node
    include xplibs.repo
    include xplibs.task
    include libs.lib.thymeleaf
    include libs.lib.xslt
    include libs.lib.asset
}
```

No `app { }` block — the auto-registered `dev` task from `com.enonic.xp.app` is what we want.

> **`lib-asset` coupling.** Any app that `include`s `libs.lib.asset` must also declare `apis: ["asset"]` in `cms/site.yaml` (or in
> the admin tool's `apis:` list for an admin-tool app). Without it, `assetUrl()` and asset-resolution calls fail at runtime with
> `API [asset] is not mounted`. The migrator does not infer this — it's a hand-edit. See SKILL.md "`cms/site.yaml` `apis:` list".

### Example B — TS app with custom `dev` task (`tutorial-intro`)

When the project drives a TS/npm build through Gradle, opt out of the auto-registered `dev` task and register your own:

```groovy
plugins {
    id 'maven-publish'
    id 'com.enonic.xp.app'
    id 'com.github.node-gradle.node' version '7.1.0'
    id 'com.enonic.defaults' version '2.1.6'
}

app {
    createDefaultDevTask = false
}

dependencies {
    include "com.enonic.lib:lib-thymeleaf:3.0.0-SNAPSHOT"

    include xplibs.content
    include xplibs.portal
    include xplibs.cluster
    include xplibs.context
    include xplibs.export
    include xplibs.project
    include xplibs.task
}

repositories {
    mavenLocal()
    mavenCentral()
    xp.enonicRepo( "dev" )
}

node {
    download = true
    version = '20.10.0'
}

apply from: "$projectDir/gradle/env.gradle"

tasks.register( 'dev', NpmTask ) {
    args = ['run', 'watch']
    dependsOn npmInstall, deploy
    environment = ['FORCE_COLOR': 'true']
}

tasks.register( 'npmBuild', NpmTask ) {
    args = ['run', isProd() ? 'minify' : 'build']
    dependsOn npmInstall
    environment = ['FORCE_COLOR'          : 'true',
                   'LOG_LEVEL_FROM_GRADLE': gradle.startParameter.logLevel.toString(),
                   'NODE_ENV'             : nodeEnvironment()]
    inputs.dir 'src/main/resources'
    outputs.dir 'build/resources/main'
}

jar.dependsOn npmBuild

processResources {
    exclude '**/.gitkeep'
    exclude '**/*.json'
    exclude '**/*.sass'
    exclude '**/*.scss'
    exclude '**/*.ts'
    exclude '**/*.tsx'
}
```

Key bits:

- `app { createDefaultDevTask = false }` — opts out of the auto `dev` task because we register our own below.
- `tasks.register('dev', NpmTask)` — custom dev task that runs `npm run watch`.
- `tasks.register('npmBuild', NpmTask)` + `jar.dependsOn npmBuild` — wires the npm build into the JAR.
- `processResources` excludes — keeps TS/SASS/JSON source files out of the produced JAR.
- `apply from: "$projectDir/gradle/env.gradle"` — pulls in helpers like `isProd()` and `nodeEnvironment()` (a small Groovy file the project
  ships; not XP-specific).

## 3. TypeScript wiring

XP 8 ships official type definitions as separate `@enonic-types/*` npm packages. For each XP library the app uses, add the matching
`@enonic-types/lib-*` to `package.json` `devDependencies`:

```json
{
  "devDependencies": {
    "@enonic-types/global": "^8",
    "@enonic-types/lib-cluster": "^8",
    "@enonic-types/lib-content": "^8",
    "@enonic-types/lib-context": "^8",
    "@enonic-types/lib-export": "^8",
    "@enonic-types/lib-portal": "^8",
    "@enonic-types/lib-project": "^8",
    "@enonic-types/lib-task": "^8"
  }
}
```

The `@enonic-types/*` packages track the XP major version. For XP 8, pin to `^8` — but always check the package page on
[npmjs.com](https://www.npmjs.com/search?q=%40enonic-types) before pinning, since the `8.x` line may not yet be published for every
lib. Do not mix `^7` and `^8` across packages in the same app.

**Flag any type package you couldn't find an XP 8-compatible version for** — don't silently pin an old major or skip the dependency.

In `tsconfig.json`, map the `/lib/xp/*` import path to those packages:

```json
{
  "compilerOptions": {
    "baseUrl": "./",
    "paths": {
      "/lib/xp/*": [
        "node_modules/@enonic-types/lib-*"
      ],
      "/*": [
        "src/main/resources/*"
      ]
    },
    "typeRoots": [
      "node_modules/@types",
      "node_modules/@enonic-types"
    ],
    "types": [
      "global"
    ]
  }
}
```

This lets controllers and `main.ts` import like `import { getContent } from '/lib/xp/content'` and get full type-checking.

## 4. Pre-migrator fixups (tricky cases)

The `xp8migrator` reads `gradle.properties` to populate `title` / `vendorName` / `vendorUrl` in the generated `enonic.yaml`. Two
common XP 7 source-tree shapes prevent that pipeline from working, and both must be fixed **before** running the migrator —
otherwise `enonic.yaml` ends up with empty metadata and you have to rerun the migrator with `-e overwrite` or hand-edit the
result.

### 4.1 Unprefixed `displayName` in `gradle.properties`

XP 7 apps sometimes use `displayName` (no prefix) instead of `appDisplayName`. The migrator only matches the prefixed form — the
unprefixed key is silently ignored and `title:` in `enonic.yaml` ends up empty.

```diff
 # gradle.properties — XP 7
 appName=com.acme.myapp
 version=1.0.0-SNAPSHOT
-displayName=My App
+appDisplayName=My App
 vendorName=Acme
 vendorUrl=https://acme.example
```

Run the migrator only after this rename. The same applies to `vendorName` / `vendorUrl` if those happen to be unprefixed in some
older templates — but the prefixed form is the common case for those two.

### 4.2 Vendor / display info hard-coded in `build.gradle`'s `app { }` block

XP 7 apps frequently wire vendor and display metadata as literals inside `build.gradle` rather than `gradle.properties`:

```groovy
// build.gradle — XP 7
app {
    name = "${appName}"
    displayName = "My App"
    vendorName = "Acme"
    vendorUrl = "https://acme.example"
    systemVersion = "${xpVersion}"
}
```

The migrator only reads `gradle.properties`, so these literals never reach `enonic.yaml`. Two valid end states; pick one
**before** running the migrator:

**Option A — lift to `gradle.properties` (recommended; the migrator handles the rest):**

```diff
 # gradle.properties
 appName=com.acme.myapp
+appDisplayName=My App
+vendorName=Acme
+vendorUrl=https://acme.example
```

```diff
 // build.gradle
-app {
-    name        = "${appName}"
-    displayName = "My App"
-    vendorName  = "Acme"
-    vendorUrl   = "https://acme.example"
-    systemVersion = "${xpVersion}"
-}
```

**Option B — skip the lift and write the values straight into `enonic.yaml` after the migrator runs.** Same end state, more
hand-editing. Choose this only if `gradle.properties` is generated/locked by some upstream tooling.

After the lift (or the post-migration hand-edit), the `app { }` block in `build.gradle` is empty and should be removed entirely
(see SKILL.md "Build files" §2). Don't leave it as `app { }` — the verified XP 8 reference apps omit it altogether.
