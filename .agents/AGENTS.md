<RULE>
嚴禁將文案（尤其是會隨狀態變化的句子）直接寫死（Hardcode）在 UI 元件中。必須將所有狀態對應的文案抽取到獨立的 config 或 constants 檔案中集中管理，以利後續維護與擴展。
</RULE>

<RULE>
整個專案必須嚴格遵守「模組化規範（Modularization）」。
1. 避免 Hardcode：無論是 UI 文案、設定值、環境變數或魔法數字（Magic Numbers），都必須抽離到專屬的常數檔（constants）、設定檔（config）或環境變數（.env）中統一管理。
2. 關注點分離（Separation of Concerns）：前端元件應保持純粹的渲染邏輯（UI Components），業務邏輯（Business Logic）、API 呼叫（Services / Hooks）與狀態管理必須各自獨立抽離。後端亦須維持 Controller（路由）、Service（業務邏輯）與 Model（資料庫）的清晰分層。
3. 高可維護性：程式碼撰寫與架構設計必須以「易於日後維護與擴展」為最高指導原則，避免寫出耦合度過高的義大利麵條程式碼。
</RULE>

<RULE>
錯誤提示與系統訊息必須保持專業與直白（例如：「系統錯誤」），嚴禁使用幼兒化、過度擬人或裝可愛的語氣（如「Oops! 腦袋打結了」）。不要自作主張加入不必要的修飾。
</RULE>
