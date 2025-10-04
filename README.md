JointSpaceVisualizer ver.2
==========================

PyQt5 + PyVista 製の 3D 距離可視化ツールです。ターゲットモデルとソースモデルの表面距離を `vtkDistancePolyDataFilter` で計算し、カラーリングや比較ビューで確認できます。UI は日本語化され、「重要事項」タブで免責事項へ同意した後に操作します。

⚠️ 重要：利用制限（アプリ内と同じ内容）
--------------------------------------

- 本ソフトウェアは医療機器ではありません。診断・治療・予防などの医学的判断に使用しないでください。
- 利用可能範囲は研究用途に限ります。臨床現場での意思決定には使用できません。
- 利用により発生したいかなる損害についても、開発側は責任を負いません。

セットアップ
-------------

1. Python 3.9 以降を用意（macOS / Windows / Linux）
2. 仮想環境を作成し依存関係をインストール
   ```bash
   python -m venv venv
   source venv/bin/activate        # Windows は venv\Scripts\activate
   python -m pip install --upgrade pip
   python -m pip install -r requirements.txt
   ```

起動方法
---------

```bash
python app/main.py
```

- 初回起動時は「重要事項」タブで同意チェックが必要です。
- macOS でウインドウが真っ白になる場合は `export QT_MAC_WANTS_LAYER=1` を試してください。
- オフスクリーンで動かす場合は `QT_QPA_PLATFORM=offscreen` を指定します。

主な機能
---------

- STL / PLY / VTK / VTP のロード（上顎骨モデル・下顎骨モデル）
- VTK による距離計算とカスタム LUT（0–5 mm のレンジを赤→青で表示）
- 表示／不透明度スライダー、デシメーション設定（処理時間短縮用）
- 距離結果の保存（VTP/PLY/STL）・カラー焼き込み PLY の出力
- スナップショットタブ、左右比較ビュー（カメラリンク ON/OFF）
- ビュー毎の明るさスライダー、Zoom/Reset ボタン、マウス／ホイール操作
- デバッグタブでアプリケーションログを参照可能

テスト / スモークテスト
-------------------------

- 最小動作確認：
  ```bash
  python scripts/smoke_test.py
  ```
- 単体テスト：
  ```bash
  python -m pip install -r requirements-dev.txt
  python -m pytest
  ```

ビルド（PyInstaller）
---------------------

```bash
python -m pip install pyinstaller
pyinstaller JointSpaceVisualizer.spec
```

`dist/JointSpaceVisualizer` にスタンドアロン実行ファイルが生成されます。

Windows インストーラー
------------------

1. Windows 上で Python 3.9+ と NSIS (makensis.exe) をインストールします。
2. PowerShell を管理者で開かず、リポジトリルートで以下を実行します。
   ```powershell
   powershell -ExecutionPolicy Bypass -File .\scripts\build_windows_installer.ps1
   ```
   - 既存の仮想環境を使いたい場合は `-ReuseVenv` を付けてください。
   - PyInstaller の成果物だけ欲しい場合は `-SkipInstaller` で NSIS パッケージングをスキップできます。
3. 完了後 `installer/windows/JointSpaceVisualizerSetup.exe` が生成されます。これが配布用セットアップです。

macOS パッケージ（未署名）
----------------------

- `installer/macos/JointSpaceVisualizer-mac.dmg` にビルド済み DMG が生成されます。Apple のコード署名・公証は行っていないため、Gatekeeper から警告が表示されます。
- 利用時は DMG を開き、`JointSpaceVisualizer.app` を `Applications` フォルダなど任意の場所にドラッグしてください。
- 初回起動は Finder でアプリを右クリック（control+クリック）→「開く」を選択し、警告ダイアログで再度「開く」を押すと起動できます。
- 信頼済みに設定した後は通常どおりダブルクリックで起動できます。未署名なので macOS のセキュリティ設定を自己責任で調整してご利用ください。

既知の注意点
--------------

- 中止ボタンは VTK の処理キャンセルを要求し、応答がない場合は数秒で安全に UI を復帰させます。完了メッセージが出るまで待ってから操作を再開してください。
- 大容量メッシュでは距離計算に時間がかかります。必要に応じてデシメーション率を下げ、処理時間と精度のバランスを調整してください。

ライセンス
-----------

TBD
