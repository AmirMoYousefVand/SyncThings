import profile
print(f"HAS_AVATARS: {profile.HAS_AVATARS}")
b64, mini = profile.generate_random_avatar()
print(f"Generated? {b64 is not None and len(b64) > 100}")
