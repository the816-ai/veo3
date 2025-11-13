# Hướng dẫn Release trên GitHub

## Tự động build với GitHub Actions

Mỗi khi bạn push code lên branch `main`, GitHub Actions sẽ tự động:
1. Build file `Veo3App.exe`
2. Lưu vào Artifacts (có thể tải về từ tab Actions)

## Tạo Release thủ công

### Cách 1: Tạo Release từ GitHub Web

1. Vào repository: https://github.com/the816-ai/veo3
2. Click **"Releases"** ở sidebar bên phải
3. Click **"Create a new release"**
4. Điền thông tin:
   - **Tag version**: `v1.0.0` (hoặc version bạn muốn)
   - **Release title**: `Veo3 v1.0.0`
   - **Description**: Mô tả các tính năng/fixes
5. Upload file `dist\Veo3App.exe` (nếu build local)
6. Click **"Publish release"**

### Cách 2: Tạo Release từ Git Tag

```bash
# Tạo tag
git tag -a v1.0.0 -m "Release version 1.0.0"
git push origin v1.0.0
```

Sau đó vào GitHub web để tạo release từ tag đó.

### Cách 3: Dùng GitHub CLI (gh)

```bash
# Cài GitHub CLI trước: https://cli.github.com/
gh release create v1.0.0 dist/Veo3App.exe --title "Veo3 v1.0.0" --notes "Initial release"
```

## Tải file EXE từ GitHub Actions

1. Vào tab **"Actions"** trên GitHub
2. Chọn workflow run mới nhất
3. Scroll xuống phần **"Artifacts"**
4. Click **"Veo3App-exe"** để tải về

## Lưu ý

- File EXE từ GitHub Actions sẽ không được ký số (unsigned)
- Người dùng có thể gặp cảnh báo SmartScreen khi tải về
- Để giảm cảnh báo, cần ký số file EXE trước khi upload lên release

