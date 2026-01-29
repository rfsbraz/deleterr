# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.5](https://github.com/rfsbraz/deleterr/compare/v0.1.4...v0.1.5) (2026-01-29)


### Bug Fixes

* hang on config errors to prevent restart loops ([#191](https://github.com/rfsbraz/deleterr/issues/191)) ([a6104b0](https://github.com/rfsbraz/deleterr/commit/a6104b04cacaeeaa2791ff7887eb76a7c3e9286e))

## [0.1.4](https://github.com/rfsbraz/deleterr/compare/v0.1.3...v0.1.4) (2026-01-29)


### Bug Fixes

* exit with non-zero code on configuration errors ([#189](https://github.com/rfsbraz/deleterr/issues/189)) ([14c1085](https://github.com/rfsbraz/deleterr/commit/14c1085f1cdf7df56f5992aa26f1a8decd67e641))
* improve test reliability and reduce CI duplication ([#185](https://github.com/rfsbraz/deleterr/issues/185)) ([34bce7c](https://github.com/rfsbraz/deleterr/commit/34bce7c7408b4b2e02c54dc4c2fd9c3df8c55aee))

## [0.1.3](https://github.com/rfsbraz/deleterr/compare/v0.1.2...v0.1.3) (2026-01-29)


### Bug Fixes

* use PAT for release-please to trigger downstream workflows ([#183](https://github.com/rfsbraz/deleterr/issues/183)) ([c0cc866](https://github.com/rfsbraz/deleterr/commit/c0cc866e02b375d00c6b3f174db7b0422a6e0edf))

## [0.1.2](https://github.com/rfsbraz/deleterr/compare/v0.1.1...v0.1.2) (2026-01-29)


### Bug Fixes

* add missing del_movie method and __getattr__ safeguard ([#181](https://github.com/rfsbraz/deleterr/issues/181)) ([4dfc05d](https://github.com/rfsbraz/deleterr/commit/4dfc05da6c11fb24a4984a806c3d2404c563bf12)), closes [#180](https://github.com/rfsbraz/deleterr/issues/180)

## [0.1.1](https://github.com/rfsbraz/deleterr/compare/v0.1.0...v0.1.1) (2026-01-29)


### Features

* **sonarr:** Add Sonarr-specific exclusions ([#174](https://github.com/rfsbraz/deleterr/issues/174)) ([6339c65](https://github.com/rfsbraz/deleterr/commit/6339c65f928e1d45f9be4117ec7ce229350849ce))


### Bug Fixes

* **ci:** use correct parameter name for PR comment action ([#175](https://github.com/rfsbraz/deleterr/issues/175)) ([9065514](https://github.com/rfsbraz/deleterr/commit/9065514ced6d9913b472983b39acd54e170c2854))
* correct pyarr method name for disk space API ([#179](https://github.com/rfsbraz/deleterr/issues/179)) ([617b47d](https://github.com/rfsbraz/deleterr/commit/617b47d8b9b914b49fe05484736f94c145c2c208))

## [0.1.0](https://github.com/rfsbraz/deleterr/compare/v0.0.20...v0.1.0) (2026-01-25)


### ⚠ BREAKING CHANGES

* The develop branch will be deleted after migration. Users should update their local repos to track main instead.
* SSL verification is now enabled by default. Users with self-signed certificates must add ssl_verify: false to their configuration.

### Features

* Add action delay support ([579b483](https://github.com/rfsbraz/deleterr/commit/579b4830827ac18f229827492ece1be69754b9da))
* Add built-in scheduler as alternative to Ofelia ([d9197d8](https://github.com/rfsbraz/deleterr/commit/d9197d860b3574ad2d5a3c2053f81322a13292f4))
* Add built-in scheduler as alternative to Ofelia ([235ad12](https://github.com/rfsbraz/deleterr/commit/235ad128e9cf7b0c6426be5d34ec22e68b1ef1a9))
* add dockerhub image support ([28b6b44](https://github.com/rfsbraz/deleterr/commit/28b6b442cabf177dc1369bbc2fb31fb260409853))
* add dockerhub image support ([693fca4](https://github.com/rfsbraz/deleterr/commit/693fca4595d7fd8fc8576e907a8656ed83f4952b))
* Add integration testing infrastructure ([2e53995](https://github.com/rfsbraz/deleterr/commit/2e53995957f66b4439245a45a2b197ada6625153))
* Add integration testing infrastructure ([80f5741](https://github.com/rfsbraz/deleterr/commit/80f574191cc2ca907e944f9bf2a6110d2ba319e7))
* Add integration tests for Deleterr deletion functionality ([be4dde3](https://github.com/rfsbraz/deleterr/commit/be4dde34d65c4d6ad6c69bf88e7d3dce1c0005f1))
* Add interactive mode to perform controlled media deletion ([386d267](https://github.com/rfsbraz/deleterr/commit/386d2675b83292b8c417102dc57364bbfb70510d))
* Add Overseerr integration for request-based media exclusions ([6374265](https://github.com/rfsbraz/deleterr/commit/63742654a2b5ec31fede5f5d08e6e042a0044e60))
* Add Overseerr integration for request-based media exclusions ([a591ed3](https://github.com/rfsbraz/deleterr/commit/a591ed37d0dd06f3a332ee9b8a1fae9bccf462bc)), closes [#6](https://github.com/rfsbraz/deleterr/issues/6)
* Add support for disk size filter ([#67](https://github.com/rfsbraz/deleterr/issues/67)) ([81eb849](https://github.com/rfsbraz/deleterr/commit/81eb849baa956b2715b8fdcefec4a5c0610b320a))
* Add support for disk size filter ([#67](https://github.com/rfsbraz/deleterr/issues/67)) ([bcfd4a5](https://github.com/rfsbraz/deleterr/commit/bcfd4a55840adcd6298e5a9cee454d8e4e27f798))
* Add support for skipping collections with watched movies ([ad307e7](https://github.com/rfsbraz/deleterr/commit/ad307e74de926e82296933c95f4daecad99cfcf8))
* add support for sonarr with standard series type ([d3669fe](https://github.com/rfsbraz/deleterr/commit/d3669fe5f7ea22060c4dfcc84f3c190996ff6434))
* add support for sorting orders ([da68eea](https://github.com/rfsbraz/deleterr/commit/da68eea27d33536e5cb7c0041ab913a56dc4938e))
* Add support to disable plex and tautulli library updates ([9ff4441](https://github.com/rfsbraz/deleterr/commit/9ff4441393983ec9e1a4f40ae97ae17b5b0ab9a7))
* add support to exclude media by title ([3bab024](https://github.com/rfsbraz/deleterr/commit/3bab024d9a568417f0c762f1c04f715c4b258f5e))
* Add trakt config support ([043bd7b](https://github.com/rfsbraz/deleterr/commit/043bd7b5c854007ea3128ea761c06cd4fba38806))
* Add watch_status support ([8c201fa](https://github.com/rfsbraz/deleterr/commit/8c201fabb4dbeb18f13bc4dfdbfacb0d549bbd3b))
* Add watch_status support ([500afb7](https://github.com/rfsbraz/deleterr/commit/500afb740cda812655bdc7e6c6e91fae0465a691))
* Add watch_status support (Sourcery refactored) ([39cfb0f](https://github.com/rfsbraz/deleterr/commit/39cfb0f8ca85e678fa9425b5262f1639c84318f1))
* **ci:** Add Docker smoke test to catch Python compatibility issues ([44f213a](https://github.com/rfsbraz/deleterr/commit/44f213ac967501c209969a0e5dae28c739bdd6ec))
* **ci:** Add Docker smoke test to catch Python compatibility issues ([4f630ae](https://github.com/rfsbraz/deleterr/commit/4f630ae0b7e02a1bd5b8d11037423a763b9ebf1b)), closes [#164](https://github.com/rfsbraz/deleterr/issues/164)
* **ci:** add pytest coverage reporting ([6af8a6a](https://github.com/rfsbraz/deleterr/commit/6af8a6a4b32adc7bda615ad92b4b68ed917b56ee))
* **ci:** Add test coverage reporting ([9d5aa08](https://github.com/rfsbraz/deleterr/commit/9d5aa080ce69e71bfa0f8f4951feb6fe548e77c5))
* **ci:** Add test coverage reporting ([d7a4fb8](https://github.com/rfsbraz/deleterr/commit/d7a4fb89eb73c26d1d63465e358e10791583e642))
* **ci:** use coveralls ([b832cba](https://github.com/rfsbraz/deleterr/commit/b832cba81289e8f4562dc0ba96ef1552fade1960))
* **ci:** use coveralls ([31c2279](https://github.com/rfsbraz/deleterr/commit/31c2279539e5956f427c953eeaeaff9c0803fa37))
* **config:** add connections validations ([2855b5a](https://github.com/rfsbraz/deleterr/commit/2855b5a67bcca79652bc66aa4a6722403ff5ea77))
* **config:** Allow loading env in yaml ([eaf5223](https://github.com/rfsbraz/deleterr/commit/eaf522333248780ee55a15d8a044fbf543fb6aae))
* **config:** Allow loading env in yaml ([eaf5223](https://github.com/rfsbraz/deleterr/commit/eaf522333248780ee55a15d8a044fbf543fb6aae))
* **justwatch:** Add justwatch module implementation ([27f5f1e](https://github.com/rfsbraz/deleterr/commit/27f5f1ea1f73a2cd119023e30dfed40d98adc382))
* **justwatch:** Add support for justwatch ([074fec6](https://github.com/rfsbraz/deleterr/commit/074fec6996783734e11d7986cca49b2c0e71f521))
* **justwatch:** Add test coverage ([9615426](https://github.com/rfsbraz/deleterr/commit/96154268fd1a7744f085780027b9bcb9d316a32c))
* **justwatch:** Integrate JustWatch streaming availability into exclusion pipeline ([2d2839c](https://github.com/rfsbraz/deleterr/commit/2d2839c76952cbf32144a24fd72791385cedb787))
* Make SSL verification configurable ([a3a50b6](https://github.com/rfsbraz/deleterr/commit/a3a50b677a297312a6a921474c9ff8a3b5dfa484))
* override plexapi config timeout ([ef44000](https://github.com/rfsbraz/deleterr/commit/ef440004de9836dc6af8b3bd58af16142e166ca0))
* **radarr:** Add movie library type support ([350ccae](https://github.com/rfsbraz/deleterr/commit/350ccae9d0e6e2c651786c61d456ac4bbaefb42a))
* **Radarr:** Add support for radarr fields filtering ([614e3e2](https://github.com/rfsbraz/deleterr/commit/614e3e271c54b10533e4b0eae330dd54d72c9a56))
* **radarr:** Add support for radarr tags ([1bb7580](https://github.com/rfsbraz/deleterr/commit/1bb758002d1cf908f4a1fb09ba2ef044033754cf))
* **radarr:** Add support to exclude movies on deletion ([005fd1b](https://github.com/rfsbraz/deleterr/commit/005fd1b055290e92465bba01d5feb45cfc4d9362))
* Remove interactive mode ([26ffddd](https://github.com/rfsbraz/deleterr/commit/26ffddd906d4fd0fb1ba8d1ecf17e493bceeac5f)), closes [#90](https://github.com/rfsbraz/deleterr/issues/90)
* **trakt:** support excluding public user lists and special lists ([b673e5d](https://github.com/rfsbraz/deleterr/commit/b673e5d94d8079a50921f02c58bef3621d1c5214))


### Bug Fixes

* Add RawAPI mock to tests after ssl_verify parameter addition ([b448df8](https://github.com/rfsbraz/deleterr/commit/b448df85a917b49af7aeb35e1cec086d8bab8893))
* Add scripts module to gitignore exception and include missing files ([9b4546b](https://github.com/rfsbraz/deleterr/commit/9b4546be0ec1188d2185c36a2448acedab6503ed))
* Add volume permissions fix for linuxserver containers in CI ([65e1ce6](https://github.com/rfsbraz/deleterr/commit/65e1ce62da2c0fc58df30fe73118594a678c4597))
* another missing patch ([d1d515c](https://github.com/rfsbraz/deleterr/commit/d1d515c81b62f5bffcf5036bfdba3743720d15ab))
* bad catch ([7e30415](https://github.com/rfsbraz/deleterr/commit/7e30415941befaf46ae61ee1b06976bc50f5a67b))
* bad directory ([30a403b](https://github.com/rfsbraz/deleterr/commit/30a403bcc23a2be985f74227c35804dbc4f6cc28))
* check show metadata per episode ([f3e7725](https://github.com/rfsbraz/deleterr/commit/f3e7725b70e595c42c9c18c832215ddf1578b74b))
* check show metadata per episode ([9af8651](https://github.com/rfsbraz/deleterr/commit/9af865119119f56de49d610cf6a5ca7f7d22c637))
* **ci:** Handle fork PRs gracefully in workflows ([e69c8c4](https://github.com/rfsbraz/deleterr/commit/e69c8c487ef45434ed307236b635cda56be3d660))
* **ci:** Pin Python version to 3.12 ([0ed1c60](https://github.com/rfsbraz/deleterr/commit/0ed1c6019900171132433e13e26087594bc5d78b))
* **ci:** Pin Python version to 3.12 and update SonarCloud action ([7dc9ff3](https://github.com/rfsbraz/deleterr/commit/7dc9ff3579dde9edee66db18b55a9e777596da74))
* **ci:** Pin Python version to 3.12 in integration_tests job ([a46de8a](https://github.com/rfsbraz/deleterr/commit/a46de8a3ba366107349b852d68df7a894d472e76))
* config path ([2f4db70](https://github.com/rfsbraz/deleterr/commit/2f4db70c59a4546588aea75d2a0ae8435b495afa))
* **config:** Fix not being able to set just added_at_threshold or last_watched_threshold ([7e3c860](https://github.com/rfsbraz/deleterr/commit/7e3c860b43a800c1b8c5c506c3d206e2ad081c68))
* **config:** Fix not being able to set just added_at_threshold or last_watched_threshold ([bc64054](https://github.com/rfsbraz/deleterr/commit/bc640545f4cf7261ed5ddd9f26eee963f09c6dc1))
* conflicting variable name ([050be06](https://github.com/rfsbraz/deleterr/commit/050be0628520a60f4ad3ba48dedfcc1e4fef0b0f))
* delay not being taken into account ([2b85e8b](https://github.com/rfsbraz/deleterr/commit/2b85e8b2c74dd698f20516f6e3663d8250c8a05c))
* Disable certificate verication to support local secured connections ([a9ded2c](https://github.com/rfsbraz/deleterr/commit/a9ded2c69552be274ece6a15d9e91bc45b452d5c))
* Downgrade simple-justwatch-python-api to 0.13 for Python 3.9 compatibility ([915dbb7](https://github.com/rfsbraz/deleterr/commit/915dbb7f3adee9c598917f5ba9420e639c11c8ac))
* duplicate test name ([5ffd6c9](https://github.com/rfsbraz/deleterr/commit/5ffd6c94d565252ca7318e1d058b43ec742b05a9))
* Ensure root folders exist before adding media in seeders ([2de431c](https://github.com/rfsbraz/deleterr/commit/2de431c29bdb85bc70d4fc24e4ce9da6af8d667c))
* ensure sonarr and radarr are well formatted ([ff989a6](https://github.com/rfsbraz/deleterr/commit/ff989a6c11782d9a8e8d3c185ffcc83191bbfc68))
* failed to unpack trakt dictionary ([4ab9a56](https://github.com/rfsbraz/deleterr/commit/4ab9a56842b2207f7eb2d998bd7820e09658a0ad))
* Failing tests ([8d91dbe](https://github.com/rfsbraz/deleterr/commit/8d91dbea030af1201b1a3c7183558be4b2732154))
* failing to check movie metadata ([3cd27e4](https://github.com/rfsbraz/deleterr/commit/3cd27e4c665be67e3f617d3a4ebaab7b03f4d59b))
* filter shows by series not taking library config into account ([bd91e76](https://github.com/rfsbraz/deleterr/commit/bd91e7698ad175143a5e11a84f7973a31d2eaa16))
* Fix crashing when disk size wasn't set ([aa3b2fe](https://github.com/rfsbraz/deleterr/commit/aa3b2fe5a9c0c7584d5ed2e3ad5129742bb44926))
* Fix crashing when disk size wasn't set ([37dc200](https://github.com/rfsbraz/deleterr/commit/37dc200c64d8e1c0284f538bcbaef335e1e63b7e))
* Fix missing patch in tests ([7222c8a](https://github.com/rfsbraz/deleterr/commit/7222c8a4fb4512c021a67913d921495cae91f12e))
* Fix monitored status check bug and add comprehensive tests ([24740c4](https://github.com/rfsbraz/deleterr/commit/24740c462aa94c2a10e276ef75eb1c339a24688e))
* Fix process_movies argument mismatch in integration test ([24b0556](https://github.com/rfsbraz/deleterr/commit/24b0556414c2553ae45787ae6c5d92e87fcacbaf))
* Fix unit tests for radarr changes ([43f097e](https://github.com/rfsbraz/deleterr/commit/43f097e0b66778c7e734a93d6f58d37216af1a68))
* Fixes crash when tautulli returned no items ([aaa43c9](https://github.com/rfsbraz/deleterr/commit/aaa43c98696eb4457e555b066fa17c5c710801d8))
* Fixes crash when tautulli returned no items ([56c2525](https://github.com/rfsbraz/deleterr/commit/56c25255d18d904cd576b0b556b7942e29aa7aa5))
* handle some edges cases when deleting episodes ([6af63e6](https://github.com/rfsbraz/deleterr/commit/6af63e6b61233bd20ee7ad44992602d03f33e064))
* hardcoded plex library name ([68cf04f](https://github.com/rfsbraz/deleterr/commit/68cf04f6a82731491689c38b4b0d966c21e69789))
* Improve integration test reliability and error handling ([0f5d8dc](https://github.com/rfsbraz/deleterr/commit/0f5d8dc8a7d23e683dd40ca624c8a81c77b6f5c9))
* Include scheduler section in auto-generated docs ([b2f4865](https://github.com/rfsbraz/deleterr/commit/b2f48650b6a42dc413e45c8c9f68ba44483f6db2))
* Install cargo and rust ([28a0192](https://github.com/rfsbraz/deleterr/commit/28a01920f4d94a98eddd5b476e6271705864b986))
* Install cargo and rust ([fc5fba0](https://github.com/rfsbraz/deleterr/commit/fc5fba0e78996a0e2b3425d03bede6bdeefcd73e))
* keyerror for items missing tvdb identifiers ([ddacf34](https://github.com/rfsbraz/deleterr/commit/ddacf34890f0cd1043724c29f52edb8c7460b055))
* load config from the docker root ([6159e52](https://github.com/rfsbraz/deleterr/commit/6159e52d484d7f6377f81331d1625eb875d92240))
* load config was a class method ([9cf95c4](https://github.com/rfsbraz/deleterr/commit/9cf95c40f64eb05d8c7a94f215c4d9f7d5e4c9c1))
* Make SSL verification configurable ([ecf94d7](https://github.com/rfsbraz/deleterr/commit/ecf94d76c253ad3e57934692cd56e2d9c3edaf40))
* Make tag matching case-insensitive in DRadarr ([a146c48](https://github.com/rfsbraz/deleterr/commit/a146c4854fdaee8aa51b27949f5ba8fafe943fa3))
* missing load config path ([7afede7](https://github.com/rfsbraz/deleterr/commit/7afede7a0743d294803a3346ddd1717a000f688f))
* missing sort case ([07c0ab0](https://github.com/rfsbraz/deleterr/commit/07c0ab0346917b3df3952cd7a909d27f6d73a572))
* missing year from tautulli ([7b587ad](https://github.com/rfsbraz/deleterr/commit/7b587ad4388ad0ebab3ed1814780c357a21f8bc7)), closes [#32](https://github.com/rfsbraz/deleterr/issues/32)
* pdb trace ([ac1cee6](https://github.com/rfsbraz/deleterr/commit/ac1cee61ec625144b2df20741a99cd5138c6c1bf))
* Prevent trakt list retrieval from crashing the application ([3eecebf](https://github.com/rfsbraz/deleterr/commit/3eecebf780b38de2f237b547fa7220622188bed9))
* provide defaults to sort ([ec30203](https://github.com/rfsbraz/deleterr/commit/ec302038336a02aedaebc3ffba780cfe579b8c34))
* pyarr does not support deleting a shows' files ([cc8843b](https://github.com/rfsbraz/deleterr/commit/cc8843b0b21ce5e1b7cd0816b771c4a7a74c0aa3))
* radarr space not being properly considered ([7864ceb](https://github.com/rfsbraz/deleterr/commit/7864ceb0cd53bfb0bad06e026653cc6984c42672))
* **radarr:** files not being deleted from disk ([9fa8171](https://github.com/rfsbraz/deleterr/commit/9fa8171e89899c2ea6bbf6017c0954388d28f14d))
* read config in utf8 ([f67c05d](https://github.com/rfsbraz/deleterr/commit/f67c05d6ee2d9b325d805cd90041fa7334a7d081))
* **refactor:** Fix some broken references ([83242fa](https://github.com/rfsbraz/deleterr/commit/83242fa955d440886a16a12e8c8fb16af40f8177))
* **refactor:** Fix test not running ([111bbff](https://github.com/rfsbraz/deleterr/commit/111bbff8e2dc9ab468ec9b8e094093ec7842d68e))
* Remove references to non-existent deleterr.arrs module ([0a816a8](https://github.com/rfsbraz/deleterr/commit/0a816a884e8bb659b7d52c511caec047c98864c8))
* Replace mutable default argument with None ([8599c45](https://github.com/rfsbraz/deleterr/commit/8599c451661506f6c76599286acaf5e2192e8f81))
* Replace mutable default argument with None ([c97c7c1](https://github.com/rfsbraz/deleterr/commit/c97c7c1f14aebf3168b777165213cc00c01711d1))
* Revert to correct Radarr exclusion list endpoint (/api/v3/exclusions) ([161b21e](https://github.com/rfsbraz/deleterr/commit/161b21e9d65b172bfdfe5908cf0ce79b4f8c2359))
* settings filename ([8aeb5cb](https://github.com/rfsbraz/deleterr/commit/8aeb5cb6c18ec2cd21f8dac90c86f647983e0ba1))
* shows without identifier returned from tautulli ([7dabd43](https://github.com/rfsbraz/deleterr/commit/7dabd43d4c8275e13637feb9d9493cd2a4e8fd12))
* temporarily using custom pytulli fork ([5f2b7bc](https://github.com/rfsbraz/deleterr/commit/5f2b7bc27b7163dff0a7337ad5f41778b8b105f9))
* tests not running ([f935b8c](https://github.com/rfsbraz/deleterr/commit/f935b8c7239d47706ecb312d59b87e39666bec01))
* trakt watchlist not working ([052ef39](https://github.com/rfsbraz/deleterr/commit/052ef3918581998cc88af9fe5bfe021f4b04f4fe))
* **trakt:** Fix Trakt lists without items crashing ([bfaa87d](https://github.com/rfsbraz/deleterr/commit/bfaa87df4ab40cfbbbc1b594fdfc37b2c3ddc203))
* **trakt:** Fix Trakt lists without items crashing ([96dddb4](https://github.com/rfsbraz/deleterr/commit/96dddb45ab108d3552bce0cea56429eae60d2c64))
* **trakt:** missing a return parameter ([48a2a7e](https://github.com/rfsbraz/deleterr/commit/48a2a7e0f25b69fef2d0978d0ea31f117fe9b9ca))
* unmatched elif ([797003e](https://github.com/rfsbraz/deleterr/commit/797003ec75d2cd5495b4622374f4e0c4a73f6c9d))
* Update DELETE endpoint URL for Radarr exclusion list cleanup ([0708584](https://github.com/rfsbraz/deleterr/commit/07085843c2021dbc2273222c98bcdb5b77d53893))
* Update JustWatch API usage for v0.13 compatibility ([7f5146d](https://github.com/rfsbraz/deleterr/commit/7f5146d147e7ed3c5afebd8c932e86dd98330f7b))
* Use 'docker compose' v2 command in conftest.py subprocess calls ([0c73756](https://github.com/rfsbraz/deleterr/commit/0c73756e5b5e091d06462a352710f0c963dc6a2e))
* Use 'docker compose' v2 command instead of 'docker-compose' ([5a19cc5](https://github.com/rfsbraz/deleterr/commit/5a19cc5188f0257b20ce0e94121eccf145cb83e9))
* Use correct Radarr API endpoint for import list exclusions ([175c8cc](https://github.com/rfsbraz/deleterr/commit/175c8cc8aa9380cfb845359092b7ce1a40dcfa65))
* Use raw API for exclusion list test since pyarr lacks support ([d6bce1a](https://github.com/rfsbraz/deleterr/commit/d6bce1ad4236df615f1ac126ad56823dc9f51b43))
* Use real TMDb/TVDB IDs and add retry logic for integration tests ([2465d85](https://github.com/rfsbraz/deleterr/commit/2465d85976b7aaf4038cc7e53d45b8df0f855818))
* Use separate volumes for movies/tv and add retry logic for root folders ([6cb5f40](https://github.com/rfsbraz/deleterr/commit/6cb5f403bdee7a06f56333ec5249953181ed713c))
* **workflow:** Fix docker image not including the right directory ([c6e8a34](https://github.com/rfsbraz/deleterr/commit/c6e8a34abdd4c7cb4cc840de36445331932cb134))
* wrong default for missing year in metadata ([4317709](https://github.com/rfsbraz/deleterr/commit/4317709312d050d48ed5b7b77ec9188c63b38a82)), closes [#32](https://github.com/rfsbraz/deleterr/issues/32)
* Wrong ids used for item matching ([0d66733](https://github.com/rfsbraz/deleterr/commit/0d66733412e110cf1ad5ce43e34bbcf132dba9e6))
* Wrong ids used for item matching ([200b01a](https://github.com/rfsbraz/deleterr/commit/200b01a467c4b66600c3cc353032d43d9b5b5f5f))
* wrong tag argument name ([70760e4](https://github.com/rfsbraz/deleterr/commit/70760e44c163eaa7bd0bbaaba55ab19cbee24acb))
* wrong tag argument name ([db26e0a](https://github.com/rfsbraz/deleterr/commit/db26e0a5cc4b42884ba881393819f7dbdbd996ee))
* yet another path fix ([5a16aed](https://github.com/rfsbraz/deleterr/commit/5a16aed42f25eb83c3182b24887a1e563619b30b))


### Miscellaneous Chores

* Migrate to trunk-based development ([#169](https://github.com/rfsbraz/deleterr/issues/169)) ([17d8d5f](https://github.com/rfsbraz/deleterr/commit/17d8d5f2699a67993bd43c96ee93037ea9b16cec))

## [0.0.20] - 2026-01-19

### Added
- Radarr-based exclusions for movie libraries (#115)
  - Exclude by Radarr tags
  - Exclude by quality profile
  - Exclude by file path
  - Exclude by monitored status
- ARM64 Docker image support for Raspberry Pi and Apple Silicon
- Better show matching with improved title comparison
- Security policy (SECURITY.md) with vulnerability reporting guidelines
- Contributing guidelines (CONTRIBUTING.md)

### Changed
- SSL verification is now configurable via `ssl_verify` setting (defaults to `false`)
- Pinned pytest-mock dependency to 3.14.1 for reproducible builds

### Fixed
- Wrong IDs used for item matching
- Wrong tag argument name in tag filtering
- Failing tests
- Prevent Trakt list retrieval from crashing the application
- Mutable default argument in `get_plex_item()` function
- Build process - install cargo and rust for dependencies

### Security
- SSL verification is now configurable, defaulting to disabled for backwards compatibility with self-signed certificates

## [0.9.0] - Previous Release

For changes prior to this changelog, please see the [GitHub Releases](https://github.com/rfsbraz/deleterr/releases) page.
