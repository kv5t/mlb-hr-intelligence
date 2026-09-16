# MLB HR Intelligence — Conceptual ER diagram (0.0-B)

The primary diagram contains **core 0.1 identity, temporal relationship and observation entities**. The second diagram shows **supporting identity/provenance references** separately to keep the domain readable. These are conceptual entities, not created tables. All `id` fields are internal immutable canonical IDs; source IDs are separate. Optionality depicts possible unknown/unassessed data, not KPI eligibility.

```mermaid
erDiagram
    SEASON ||--o{ GAME : contains
    TEAM ||--o{ GAME : home_team
    TEAM ||--o{ GAME : away_team
    VENUE o|--o{ GAME : hosts_when_known
    PLAYER ||--o{ PLAYER_TEAM_AFFILIATION : has_history
    TEAM ||--o{ PLAYER_TEAM_AFFILIATION : includes
    SEASON o|--o{ PLAYER_TEAM_AFFILIATION : optional_scope
    GAME ||--o{ GAME_LIFECYCLE_EVENT : has_history
    GAME ||--o{ GAME_DATA_COVERAGE : has_assessments
    GAME ||--o{ PLAYER_GAME_PARTICIPATION : has_assessed_players
    PLAYER ||--o{ PLAYER_GAME_PARTICIPATION : has_game_state
    TEAM ||--o{ PLAYER_GAME_PARTICIPATION : represented_by
    GAME ||--o{ PLATE_APPEARANCE : contains
    PLAYER ||--o{ PLATE_APPEARANCE : batter
    PLAYER o|--o{ PLATE_APPEARANCE : pitcher_when_known
    TEAM ||--o{ PLATE_APPEARANCE : batting_team
    TEAM ||--o{ PLATE_APPEARANCE : fielding_team
    PLATE_APPEARANCE ||--o| HOME_RUN_EVENT : yields_at_most_one

    SEASON {
        uuid id PK
        int year UK
        date starts_on "optional"
        date ends_on "optional"
    }
    TEAM {
        uuid id PK
        string display_name "sourced"
        string abbreviation "sourced"
        int mlb_id "optional unique lookup"
    }
    PLAYER {
        uuid id PK
        string display_name "sourced"
        string bats "L/R/S/unknown"
        int mlb_id "optional unique lookup"
        string throws "L/R/unknown"
    }
    VENUE {
        uuid id PK
        string name "sourced"
        string timezone_id "optional"
        int mlb_id "optional unique lookup"
    }
    PLAYER_TEAM_AFFILIATION {
        uuid id PK
        uuid player_id FK
        uuid team_id FK
        date effective_from_date "optional"
        date effective_to_date_exclusive "optional"
        string boundary_precision "optional"
    }
    GAME {
        uuid id PK
        uuid season_id FK
        uuid home_team_id FK
        uuid away_team_id FK
        uuid venue_id "optional FK"
        string game_type
        int mlb_game_pk "optional unique lookup"
        date official_date "optional"
        datetime scheduled_start_at_utc "optional"
        datetime actual_start_at_utc "optional"
        datetime completed_at_utc "optional"
        string status
        string finality
        int scheduled_game_number "optional"
    }
    GAME_LIFECYCLE_EVENT {
        uuid id PK
        uuid game_id FK
        string event_kind
        datetime effective_at_utc "optional"
        datetime recorded_at_utc
        datetime scheduled_start_at_utc "optional"
    }
    GAME_DATA_COVERAGE {
        uuid id PK
        uuid game_id FK
        string domain
        string state
        datetime assessed_at_utc
    }
    PLAYER_GAME_PARTICIPATION {
        uuid id PK
        uuid game_id FK
        uuid player_id FK
        uuid team_id FK
        string participation_state
        boolean started "optional"
        int reported_pa_count "optional"
        string pa_coverage
    }
    PLATE_APPEARANCE {
        uuid id PK
        uuid game_id FK
        uuid batter_id FK
        uuid pitcher_id "optional FK"
        uuid batting_team_id FK
        uuid fielding_team_id FK
        int game_pa_ordinal "optional unique per game"
        string outcome_category
        string batter_side_used "optional"
        string pitcher_hand_used "optional"
    }
    HOME_RUN_EVENT {
        uuid id PK
        uuid plate_appearance_id "unique FK"
    }
```

`PlayerTeamAffiliation` is created only from dated temporal association evidence; a single game appearance does not establish its interval. `Team` has two distinct roles in `Game`. `PlateAppearance` likewise has batting and fielding team roles and a nullable pitcher reference. `PlayerGameParticipation` rows are unique by `(game, player, team)` and express assessed states; their absence means unassessed. `GameDataCoverage` is a current assessment per game/domain, with assessment history handled by the future ingestion design. `HomeRunEvent` obtains batter, game and team through its one PA, avoiding competing references.

## Supporting/provenance references

```mermaid
erDiagram
    PROVIDER ||--o{ EXTERNAL_IDENTIFIER : issues
    PROVIDER ||--o{ SOURCE_RECORD_REFERENCE : supplies
    SOURCE_RECORD_REFERENCE ||--o{ FACT_SOURCE_LINK : supports_or_conflicts

    PROVIDER {
        uuid id PK
        string code UK
    }
    EXTERNAL_IDENTIFIER {
        uuid id PK
        uuid provider_id FK
        string entity_kind
        string external_value
        uuid canonical_entity_id "typed target"
        string resolution_state
    }
    SOURCE_RECORD_REFERENCE {
        uuid id PK
        uuid provider_id FK
        string source_record_key "when available"
        datetime retrieved_at_utc
        string payload_reference "optional"
    }
    FACT_SOURCE_LINK {
        uuid id PK
        uuid source_record_reference_id FK
        string canonical_entity_kind
        uuid canonical_entity_id "typed target"
        string field_or_claim "optional"
        string relation
    }
```

`ExternalIdentifier.canonical_entity_id` and `FactSourceLink.canonical_entity_id` are **typed references** to an existing core entity, not ordinary FKs to every entity shown in the primary diagram. Their target integrity requires domain/ingestion validation; the diagram deliberately avoids false direct FK claims. A canonical fact can have multiple source links and a source record can support several facts. Provider authority is in PROVIDER_STRATEGY; ingestion reconciliation is specified in RECONCILIATION_POLICY and INGESTION_ARCHITECTURE.

## Future extensions outside the core ERD

- **0.2:** Pitch/batted-ball tracking events link to a PA and, for an HR, may reconcile to `HomeRunEvent`; unmatched source observations retain their provenance.
- **0.3:** Time-aware park/roof and weather observations relate to venue/game/time; matchup joins use PA batter/pitcher and actual event sides.
- **0.4:** Versioned model artifacts reference input snapshots and subjects without becoming Player or Game identity fields.

See [DATA_MODEL.md](DATA_MODEL.md) for fields, time semantics and unresolved questions, and [DATA_INVARIANTS.md](DATA_INVARIANTS.md) for validation rules.
