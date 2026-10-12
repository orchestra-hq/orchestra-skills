{# macros/generate_schema_name.sql — dbt's default plus one branch: the `ci` target writes every
   model into <ci target schema>_<DBT_CI_SCHEMA_SUFFIX>, e.g. ci_123 for PR 123.
   If the project already overrides this macro, add only the `ci` branch to it. #}
{% macro generate_schema_name(custom_schema_name, node) -%}

    {%- set default_schema = target.schema -%}

    {%- if target.name == "ci" -%}

        {{ default_schema }}_{{ env_var('DBT_CI_SCHEMA_SUFFIX') }}

    {%- elif custom_schema_name is none -%}

        {{ default_schema }}

    {%- else -%}

        {{ default_schema }}_{{ custom_schema_name | trim }}

    {%- endif -%}

{%- endmacro %}
