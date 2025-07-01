#!/bin/bash

check_sha256() {
    local file="$1"
    local expected_hash="$2"

    if [[ ! -f "$file" ]]; then
        echo "File not found: $file"
        return 2
    fi

    local actual_hash
    actual_hash=$(sha256sum "$file" | awk '{print $1}')

    if [[ "$actual_hash" == "$expected_hash" ]]; then
        echo "SHA256 hash matches."
        return 0
    else
        echo "SHA256 hash mismatch!"
        echo "Expected: $expected_hash"
        echo "Actual:   $actual_hash"
        return 1
    fi
}

set -x
# TODO: make better path that one owned by root
VDI_PATH=/mnt/vdidelete

download() {
    URL="https://sediriw-store.s3.us-west-2.amazonaws.com/2tb.MBR.Windows.By.Itself.vdi?response-content-disposition=inline&X-Amz-Content-Sha256=UNSIGNED-PAYLOAD&X-Amz-Security-Token=IQoJb3JpZ2luX2VjEIz%2F%2F%2F%2F%2F%2F%2F%2F%2F%2FwEaCXVzLXdlc3QtMiJHMEUCICQ0ZOkNt7cQWzFTC4cdk2V6%2B%2Frn8kH2Qe3r59t9KWwdAiEArhBfsHkT6VqiRBQl5bTDvJHjwAAvszyD86RLrPeV1gMqwgMIlf%2F%2F%2F%2F%2F%2F%2F%2F%2F%2FARAAGgw3OTk0OTM0MjI1OTAiDAWyOm%2B1a3419YawDCqWA4FBbeuJfixaZM3bfGT8cKgOZ1B9giZCRE29NJ5QVph7xV9NUezZa7yUcbqHizwRvcyzXQw1mbf1fTUG%2Fwl6HONSpjqMbgjgiWM1JlPre4VsmBzTQz%2FT17WKLPZEfQJ1WaxIvpNRp4z7tnxYJkcaM6YHSdxz1Cu%2BNbrT1RGka6nSWy7YVZd5Kown%2B0GKYPEyw1dTbNhkXYLkHWQALnVOcYUT1BscSmoqKXSCBTB%2Fo7Jepn1zQwCN%2BcIryrjk%2FgBEPoqYUYG0MU4JVmCsXAxn7DZHXO6jOQfKa1V%2BK6fOeeba%2B0FalrLIFqIBitvevXFv%2Bzmce0BSIXIG5mJNCXjjmTkTgKu4dv%2FTwX5Ug2KyGOvJiKd2roj6CIH9rqFAb8N9eJ8JLcnU%2BCVUvvb%2Fog7fDvMITyRNSO5oQ4gNdLP1wH4Tj%2FMHn3Tw1GTdD3c44ycEVsZC0OXxQTE03jr2Ja0gjlHXoXY8gUYy3zFX3znaQKOB7oR7hz5NP0BFRtiUvurXaF4PmE36JZEaU1ZfZH2Cm8YhynuGrJQw0dC1wwY63gJG9vef6gMVOhAMqzfrZqaUepRCBYVyh4t1FKc0pnGqk6WgtKmIiStjsw7tbVvAX9NFIXJ6IsgqBkH7QTTUDCowymI6ORbKKquZy5qKqMpUyi3%2FDfpzYGUNOHVWbopu3Adz2RQQS4NUcjTaHUP7LImjcEXBbXpNlM7KUq%2FUT29slt5kFxz%2FWDXKMn%2BNgUa6Oh9jGnIAuBTOEiIRYJKjkFaI4vfQFzw8HyUFTrIyHg4WfTKSnz9fSv33K%2FzqusNiTSa6wNHxHJ9ky0ZF6fq1XxDXjjSvg6gW8Iq59jD%2Bcw7ouAi2%2FiNVC16jPUjLx0zQDugNG4VusjALpIvuanSCrB4gheEkFgHht6b98%2FU9bdx9rtC4WELCOzCtDRHhT7rjfRSPsEuwEbCH%2FPCH10q%2FECZjZ3IzWlSa8DwjqoUoI8glspSCun9RCXCOrXMWdtFehibGn7fvaeUR1HRSloDWAA%3D%3D&X-Amz-Algorithm=AWS4-HMAC-SHA256&X-Amz-Credential=ASIA3UJMFPX7EZTDHFT7%2F20250708%2Fus-west-2%2Fs3%2Faws4_request&X-Amz-Date=20250708T193833Z&X-Amz-Expires=43200&X-Amz-SignedHeaders=host&X-Amz-Signature=8106ac39839e8b85a002e70a9409ccb99ea526d0756ad7d19f9ef9605afe6bd8"
    sudo mkdir -p "$VDI_PATH"
    sudo chmod 777 "$VDI_PATH"
    aria2c --summary-interval=1 "$URL" -d "$VDI_PATH"
}


check_sha256 "$VDI_PATH/2tb.MBR.Windows.By.Itself.vdi" "13e83f17ac565cf92b1568ea4af54fbba14c6f599de93cf3a65ef42ea142ae60"
if [[ $? -ne 0 ]]; then
    rm "$VDI_PATH/2tb.MBR.Windows.By.Itself.vdi"
    download
fi
