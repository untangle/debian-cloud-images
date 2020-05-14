#!/bin/bash

get_ami_id() {
  local upload_manifest=$1
  jq -M -r '.items[0].data.ref' < $upload_manifest
}

get_snapshot_id() {
  local ami_id=$1
  # FIXME: variabilize region
  aws ec2 --region us-east-1 describe-images --image-id $ami_id | jq -M -r '.Images[0].BlockDeviceMappings[0].Ebs.SnapshotId'
}

share_ami() {
  local amiid="$1"
  local snapid="$2"
  local accountid="$3"

  aws ec2 modify-image-attribute --image-id ${amiid} --launch-permission "Add=[{UserId=${accountid}}]"
  aws ec2 modify-snapshot-attribute --snapshot-id ${snapid} --attribute createVolumePermission --operation-type add --user-ids ${accountid}
}

## main
upload_manifest=$1

export AWS_DEFAULT_REGION=us-east-1

ami_id=$(get_ami_id $upload_manifest)
snap_id=$(get_snapshot_id $ami_id)

# FIXME: get that list from a command-line switch
for account_id in 612726942234 679593333241 684062674729 ; do
  share_ami $ami_id $snap_id $account_id
done
