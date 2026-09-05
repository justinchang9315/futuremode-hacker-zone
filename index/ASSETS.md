# 素材與授權紀錄

公開 GitHub 儲存庫前，所有非自行製作素材都必須能追溯來源並符合再散布條款。

| 檔案 | 用途 | 來源 | 作者 | 授權 | 是否允許再散布 |
| --- | --- | --- | --- | --- | --- |
| `toon_cat.glb` | 學習島與角色房間的 3D 小芽 | [Sketchfab：Toon Cat FREE](https://sketchfab.com/3d-models/toon-cat-free-b2bd1ee7858444bda366110a2d960386) | [Omabuarts Studio](https://sketchfab.com/omabuarts) | [CC BY 4.0](http://creativecommons.org/licenses/by/4.0/) | **可以**，須署名 |

Sketchfab 對這個模型的授權說明是 "Author must be credited. Commercial use is allowed."

## 必須保留的署名

CC BY 4.0 要求標示作者。目前放在**家長專區底部**（`index.html` 的 `#parentModal`）：

```text
3D 角色 "Toon Cat FREE" by Omabuarts Studio，依 CC BY 4.0 使用。
```

三個連結（模型頁、作者頁、授權條款）都要保留，這是 CC BY 的標準署名要素：標題、作者、來源、授權。**移除這段等於失去使用授權**，改版時不要順手刪掉。

## 來源是怎麼確認的

專案早期曾誤記來源為 CGTrader。CGTrader 的 Royalty Free License 禁止再散布模型原始檔，若屬實就不能公開這個儲存庫。實際比對後確認並非如此：

| 證據 | 結果 |
| --- | --- |
| `glTF asset.generator` | `Sketchfab-12.66.0` —— 檔案由 Sketchfab 匯出器產生，CGTrader 不會產生此標記 |
| 三角面數 | 本檔 2636＝Sketchfab 頁面標示 2636，完全一致 |
| 動畫／材質／貼圖數 | 皆為 1，與該模型一致 |
| 頂點數 | 本檔 1810 vs 頁面 1358 —— 差異來自匯出 glTF 時 UV／法線接縫拆點，屬正常現象，非不同模型 |

重新驗證的方法：解析 GLB 的 JSON chunk，讀 `asset.generator`，並用 `accessors[primitive.indices].count / 3` 計算面數。

## 其他素材

目前沒有其他第三方素材。介面圖示使用系統 emoji，字型使用 Google Fonts 與系統字型，未打包進儲存庫。

## 新增素材時

1. 先確認授權允許修改、展示，以及把原始檔放進公開儲存庫。
2. 把來源網址、作者、授權與再散布結論填進上表。
3. 若授權要求署名，同時更新家長專區的署名區塊。
4. 若無法確認權利，維持私人儲存庫，或改用有明確授權的替代素材。
