import hashlib
import itertools

TARGET_MD5 = "470af1bd61ae8be30ac5b5ee61e487c7"

fields = {
    "sesPort": "8087",
    "netDiskUrl": "http://192.168.31.221:8080/NetDiskWeb",
    "usageMode": "0",
    "mdmPort": "8083",
    "sesIp": "122.9.161.134",
    "checkResult": "0",
    "mdmScheme": "http",
    "isMasterSlaveModel": "0",
    "umcMode": "0"
}

def md5(s):
    return hashlib.md5(s.encode('utf-8')).hexdigest()

separators = ["", ":", "|", ","]

tested = 0
for r in range(2, len(fields)+1):
    for keys in itertools.permutations(fields.keys(), r):
        values = [fields[k] for k in keys]
        for sep in separators:
            joined = sep.join(values)
            tested += 1
            digest = md5(joined)
            if digest == TARGET_MD5:
                print("✅ MATCH FOUND!")
                print("Keys:", keys)
                print("Separator:", repr(sep))
                print("Joined string:", joined)
                print("MD5:", digest)
                exit(0)

print(f"❌ No match found after testing {tested} combinations.")