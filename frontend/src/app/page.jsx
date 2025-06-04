'use client';
import { useState } from 'react';

export default function Home() {
  // Google連携ワークフロー用の状態変数のみ残す
  const [numberOfCopies, setNumberOfCopies] = useState(1); // デフォルト値を1に設定
  const [inputValue, setInputValue] = useState(numberOfCopies.toString());
  const [workflowIsLoading, setWorkflowIsLoading] = useState(false);
  const [workflowResults, setWorkflowResults] = useState(null);
  const [workflowError, setWorkflowError] = useState('');

  const handleInputChange = (e) => {
    setInputValue(e.target.value);
  };

  const handleInputBlur = () => {
    const numericValue = parseInt(inputValue, 10);
    if (!isNaN(numericValue) && numericValue >= 1) {
      setNumberOfCopies(numericValue);
      setInputValue(numericValue.toString());
    } else {
      setNumberOfCopies(1);
      setInputValue("1");
    }
  };

  // Google連携ワークフロー実行関数
  const handleExecuteWorkflow = async () => {
    setWorkflowIsLoading(true);
    setWorkflowResults(null);
    setWorkflowError('');

    if (numberOfCopies <= 0) {
        setWorkflowError('複製数は1以上である必要があります。');
        setWorkflowIsLoading(false);
        return;
    }

    try {
      const response = await fetch('https://aim-instructionsdocs-6lrvrksmj.vercel.app/api/execute_workflow', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ number_of_copies: parseInt(numberOfCopies, 10) }), // 数値型で送信
      });

      const data = await response.json();

      if (!response.ok) {
        throw new Error(data.detail || 'ワークフローの実行に失敗しました。');
      }
      
      setWorkflowResults(data);
    } catch (error) {
      console.error('Workflow Error:', error);
      setWorkflowError(error.message || 'ワークフローの実行中に不明なエラーが発生しました。');
    }
    setWorkflowIsLoading(false);
  };

  // ユーザーインターフェースの構築
  return (
    <div className="p-8 max-w-2xl mx-auto"> {/* 画面幅を制限し中央寄せ */}
      <header className="mb-8 text-center"> {/* ヘッダーセクション */} 
        <h1 className="text-3xl font-bold text-gray-800">編集指示書自動作成ツール</h1>
        <p className="text-gray-600 mt-2">作成する指示書の数を入力すると、動画ファイルや音声ファイルを自動取得し、そのファイル内容を記載した指示書を自動作成します。</p>
      </header>
      
      <main> {/* メインコンテンツセクション */} 
        <section className="bg-white shadow-md rounded-lg p-6">
          <div className="space-y-4">
            <div className="flex flex-col items-stretch gap-3 p-4 bg-gray-50 rounded-lg shadow"> {/* 親要素: スマホ・PC問わず縦積み、子要素は幅いっぱい */}
              <label
                htmlFor="numberOfCopies"
                className="font-medium text-gray-700 text-left text-sm sm:text-base" /* ラベルは左寄せ、フォントサイズ調整 */
              >
                ドキュメント複製数:
              </label>
              <input
                id="numberOfCopies"
                type="number"
                value={inputValue}
                onChange={handleInputChange}
                onBlur={handleInputBlur}
                min="1"
                inputMode="numeric" 
                pattern="[0-9]*"  
                className="border border-gray-300 rounded px-3 py-3 text-lg focus:ring-2 focus:ring-purple-500 focus:border-purple-500 transition duration-150 w-full appearance-textfield" 
              />
              <button
                onClick={handleExecuteWorkflow}
                disabled={workflowIsLoading}
                className="w-full bg-purple-600 hover:bg-purple-700 text-white px-6 py-3 rounded-md font-semibold disabled:opacity-60 disabled:cursor-not-allowed transition duration-150 ease-in-out shadow-sm text-lg" 
              >
                {workflowIsLoading ? (
                  <>
                    <svg className="animate-spin -ml-1 mr-3 h-5 w-5 text-white inline" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                      <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                      <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                    </svg>
                    実行中...
                  </>
                ) : '実行'}
              </button>
            </div>

            {workflowError && (
              <div role="alert" className="mt-4 p-3 bg-red-50 border border-red-200 text-red-700 rounded-md">
                <p className="font-medium">エラーが発生しました:</p>
                <p className="text-sm">{workflowError}</p>
              </div>
            )}

            {workflowResults && (
              <div className="bg-gray-50 p-4 rounded-lg border border-gray-200 mt-6 space-y-4">
                <h3 className="text-xl font-semibold text-gray-700 border-b pb-2">ワークフロー実行結果:</h3>
                {workflowResults.message && 
                  <p className="px-3 py-2 bg-green-50 text-green-700 border border-green-200 rounded-md font-semibold">
                    {workflowResults.message}
                  </p>
                }
                
                {workflowResults.details && Object.entries(workflowResults.details).map(([key, value]) => (
                  <div key={key} className="border-t border-gray-200 pt-3 mt-3 first:border-t-0 first:pt-0 first:mt-0">
                    <h4 className="font-semibold text-gray-600 capitalize mb-1">{key.replace(/_/g, ' ').replace(/step[0-9] /i, '')}:</h4>
                    {typeof value === 'string' ? (
                        value.split('\n').map((line, index) => (
                            <p key={index} className="text-sm text-gray-700 whitespace-pre-wrap break-words">
                                {line.startsWith('http') ? 
                                    <a href={line} target="_blank" rel="noopener noreferrer" className="text-blue-600 hover:text-blue-700 underline transition duration-150">{line}</a> 
                                    : line}
                            </p>
                        ))
                    ) : Array.isArray(value) ? (
                        <ul className="list-disc list-inside pl-4 space-y-1">
                            {value.map((item, index) => <li key={index} className="text-sm text-gray-700">{item}</li>)}
                        </ul>
                    ) : (
                        <pre className="text-sm text-gray-700 whitespace-pre-wrap bg-gray-100 p-2 rounded-md break-all">{JSON.stringify(value, null, 2)}</pre>
                    )}
                  </div>
                ))}
              </div>
            )}
          </div>
        </section>
      </main>
    </div>
  );
}