///|
test "RFC 1321 vectors and nondestructive digest" {
  let md5 = Md5::new()
  assert_eq(
    md5.digest(),
    b"\xd4\x1d\x8c\xd9\x8f\x00\xb2\x04\xe9\x80\x09\x98\xec\xf8\x42\x7e",
  )
  md5.update(b"a")
  assert_eq(
    md5.digest(),
    b"\x0c\xc1\x75\xb9\xc0\xf1\xb6\xa8\x31\xc3\x99\xe2\x69\x77\x26\x61",
  )
  md5.update(b"b")
  md5.update(b"c")
  assert_eq(
    md5.digest(),
    b"\x90\x01\x50\x98\x3c\xd2\x4f\xb0\xd6\x96\x3f\x7d\x28\xe1\x7f\x72",
  )
  let long = Md5::new()
  for _ in 0..<1000 {
    long.update(Bytes::makei(1000, _ => b'a'))
  }
  assert_eq(
    long.digest(),
    b"\x77\x07\xd6\xae\x4e\x02\x7c\x70\xee\xa2\xa9\x35\xc2\x29\x6f\x21",
  )
}

///|
test "MD5 padding boundary vector" {
  let md5 = Md5::new()
  md5.update(b"ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789")
  assert_eq(
    md5.digest(),
    b"\xd1\x74\xab\x98\xd2\x77\xd9\xf5\xa5\x61\x1c\x2c\x9f\x41\x9d\x9f",
  )
}
