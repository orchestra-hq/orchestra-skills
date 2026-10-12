{# macros/drop_ci_schema.sql — drops the PR's CI schema. Reuses generate_schema_name so it always
   matches the schema CI built into. Must be on the default branch: the PR branch may be deleted.
   On dbt 1.12+ `dbt run-operation --sql 'drop schema if exists ...'` works without this macro. #}
{% macro drop_ci_schema() %}
    {% set schema = generate_schema_name(none, none) | trim %}
    {% do adapter.drop_schema(api.Relation.create(database=target.database, schema=schema)) %}
    {{ log("Dropped schema " ~ schema, info=true) }}
{% endmacro %}
