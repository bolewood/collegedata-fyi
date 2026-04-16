export function Footer() {
  return (
    <footer className="mt-auto border-t border-gray-200 bg-gray-50">
      <div className="mx-auto max-w-5xl px-4 py-8 text-sm text-gray-500">
        <div className="flex flex-col sm:flex-row justify-between gap-4">
          <div>
            <p className="font-medium text-gray-700">collegedata.fyi</p>
            <p>
              An open-source archive of U.S. college Common Data Set documents.
            </p>
          </div>
          <div className="flex gap-6">
            <a
              href="https://github.com/bolewood/collegedata-fyi"
              target="_blank"
              rel="noopener noreferrer"
              className="hover:text-gray-700"
            >
              GitHub
            </a>
            <a
              href="https://api.collegedata.fyi/rest/v1/"
              target="_blank"
              rel="noopener noreferrer"
              className="hover:text-gray-700"
            >
              API
            </a>
            <a href="/about" className="hover:text-gray-700">
              About
            </a>
          </div>
        </div>
        <p className="mt-4 text-xs text-gray-400">
          MIT License. Data sourced from individual school IR offices via the
          Common Data Set Initiative template.
        </p>
      </div>
    </footer>
  );
}
