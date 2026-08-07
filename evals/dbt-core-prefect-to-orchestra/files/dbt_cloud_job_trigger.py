from prefect import flow
from prefect_dbt.cloud import DbtCloudCredentials
from prefect_dbt.cloud.jobs import DbtCloudJob


@flow
def dbt_cloud_flow():
    dbt_cloud_job = DbtCloudJob(
        dbt_cloud_credentials=DbtCloudCredentials.load("dbt-cloud-prod"),
        job_id=987654,
        account_id=54321,
    )
    dbt_cloud_job.trigger()


if __name__ == "__main__":
    dbt_cloud_flow()
