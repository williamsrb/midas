# How to verify i99x-group review environment (I99X-361 bootstrap)

## Purpose
Confirm the XP8 group-site review deployment is up after CI Helm deploy.

## Prerequisites
- Review branch pipeline green (`review_build` → `review_minio` → `review_deploy`)
- No `/admin` login required for the public homepage check

## Steps
1. Open `https://review.i99x-group.k8s.seeds.no/`
2. Expect HTTP 200 and an XP HTML document (title/content may be minimal or debug during early bootstrap)
3. Optional: open GitLab project `https://git.seeds.no/seeds/i99x-group` (needs GitLab web session) for source evidence:
   - `xp/gradle.properties` → `appName = no.seeds.99x`
   - `xp/src/main/resources/cms/content-types/` → 12 legacy folders
   - Pipelines → latest `review` pipeline Passed

## Notes / blockers
- Public homepage may render with transparent body background; force white background before screenshots if the capture looks black
- `/admin` returns 401 until XP admin credentials are available

## Sample data
- Review base URL: `https://review.i99x-group.k8s.seeds.no/`
- Example green pipeline: `https://git.seeds.no/seeds/i99x-group/-/pipelines/85449`
